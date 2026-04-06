# Orchestrator Agent — routes student queries to the right agent and coordinates multi-agent collaboration
import os
import asyncio
from typing import Optional

from langchain_openai import ChatOpenAI

from agents.tutor import TutorAgent
from agents.analytics import AnalyticsAgent
from agents.support import SupportAgent
from utils.session import StudentSession


# System prompt used to classify the student's query intent
ROUTER_SYSTEM = """You are a query router for a multi-agent academic assistant.
Classify the student's query into exactly one of these categories:
- TUTOR: academic questions, explanations, concept help, summarization, quiz requests
- ANALYTICS: performance review, progress check, score analysis, study plan based on performance
- SUPPORT: motivation, stress, study tips, time management, general wellbeing
- COLLABORATION: complex queries needing both tutoring and analytics/support

Respond with only the category name."""


# Orchestrator class — routes queries and runs multi-agent collaboration when needed
class OrchestratorAgent:

    name = "OrchestratorAgent"
    _version = 3  # bump this when the interface changes to invalidate cached instances

    def __init__(
        self,
        session: StudentSession,
        llm: Optional[ChatOpenAI] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.session = session
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
        self._api_key = openai_api_key or os.getenv("OPENAI_API_KEY", "")

        # Initialize the three specialized agents
        self.tutor = TutorAgent(llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.3))
        self.analytics = AnalyticsAgent(llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.4))
        self.support = SupportAgent(llm=ChatOpenAI(model="gpt-4o-mini", temperature=0.6))
        self._retriever = None  # set via set_retriever() after the store is ready

    # Function to pass a retriever to the tutor agent and store a reference for quiz RAG
    def set_retriever(self, retriever):
        self._retriever = retriever
        self.tutor.set_retriever(retriever)

    # Function to classify the student's intent using the LLM
    def _classify_intent(self, query: str) -> str:
        response = self.llm.invoke([
            ("system", ROUTER_SYSTEM),
            ("human", query),
        ])
        intent = response.content.strip().upper()
        valid = {"TUTOR", "ANALYTICS", "SUPPORT", "COLLABORATION"}
        return intent if intent in valid else "TUTOR"

    # Function to route a query to the appropriate agent
    def route(self, query: str, web_search: bool = False) -> dict:
        intent = self._classify_intent(query)
        self.session.add_message("user", query)

        # Optionally fetch live web context via DuckDuckGo
        web_context = ""
        if web_search:
            try:
                from langchain_community.tools import DuckDuckGoSearchRun
                web_context = DuckDuckGoSearchRun().run(query)
            except Exception:
                web_context = ""

        if intent == "TUTOR":
            result = self.tutor.answer(query, web_context=web_context)
            self.session.add_message("assistant", result["answer"], agent_name="TutorAgent")
            self.session.add_topic(self._extract_topic(query))
            return result

        elif intent == "ANALYTICS":
            result = self.analytics.analyze(self.session)
            self.session.add_message("assistant", result["analysis"], agent_name="AnalyticsAgent")
            return {
                "agent": "AnalyticsAgent",
                "answer": result["analysis"],
                "summary": result["summary"],
            }

        elif intent == "SUPPORT":
            result = self.support.respond(query)
            self.session.add_message("assistant", result["answer"], agent_name="SupportAgent")
            return result

        elif intent == "COLLABORATION":
            return self._run_collaboration(query)

        return {"agent": self.name, "answer": "I couldn't process that request. Please try again."}

    # Function to extract the main topic from a query in 2-4 words
    def _extract_topic(self, query: str) -> str:
        response = self.llm.invoke([
            ("system", "Extract the main academic topic from this query in 2-4 words. Respond only with the topic."),
            ("human", query),
        ])
        return response.content.strip()

    # Function to run a multi-agent collaboration using AutoGen when a complex query needs both tutor and analytics
    def _run_collaboration(self, query: str) -> dict:
        session_summary = self.session.get_analytics_summary()

        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.teams import RoundRobinGroupChat
        from autogen_agentchat.conditions import TextMentionTermination
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        model_client = OpenAIChatCompletionClient(
            model="gpt-4o-mini",
            api_key=self._api_key,
        )

        tutor_bot = AssistantAgent(
            name="TutorBot",
            model_client=model_client,
            system_message=(
                "You are an expert academic tutor. Answer the student's question clearly "
                "and thoroughly. End your message with the tag TUTOR_DONE."
            ),
        )

        analytics_bot = AssistantAgent(
            name="AnalyticsBot",
            model_client=model_client,
            system_message=(
                f"You are a learning analytics expert. After TutorBot answers, "
                f"add personalized insights based on this student's data:\n"
                f"- Topics studied: {session_summary['topics_studied']}\n"
                f"- Average quiz score: {session_summary['average_score']}%\n"
                f"- Weak areas: {session_summary['weak_areas']}\n\n"
                f"Connect the tutor's answer to the student's learning gaps and suggest "
                f"next steps. End your message with COLLABORATION_COMPLETE."
            ),
        )

        termination = TextMentionTermination("COLLABORATION_COMPLETE")
        team = RoundRobinGroupChat(
            participants=[tutor_bot, analytics_bot],
            termination_condition=termination,
            max_turns=4,
        )

        # Run the async team in a synchronous context
        result_messages = asyncio.run(self._run_team(team, query))

        # Combine all messages and clean up termination tags
        combined = "\n\n---\n\n".join(m for m in result_messages if m.strip())
        combined = combined.replace("TUTOR_DONE", "").replace("COLLABORATION_COMPLETE", "").strip()

        self.session.add_message("assistant", combined, agent_name="Collaboration")
        return {
            "agent": "Collaboration (TutorBot + AnalyticsBot)",
            "answer": combined,
            "sources": [],
        }

    # Async helper to run the AutoGen team and collect all messages
    async def _run_team(self, team, query: str) -> list[str]:
        messages = []
        async for event in team.run_stream(task=query):
            if hasattr(event, "content") and isinstance(event.content, str):
                messages.append(event.content)
        return messages

    # Function to delegate quiz generation to the tutor agent.
    # Retrieves relevant course material context first, then returns a ready-to-use
    # list of question dicts (question, options dict, answer letter) — already shuffled.
    def handle_quiz(self, topic: str, num_questions: int = 3) -> list:
        context = ""
        if self._retriever:
            try:
                docs = self._retriever.invoke(topic)
                context = "\n\n".join(doc.page_content for doc in docs[:4])
            except Exception:
                context = ""
        questions = self.tutor.generate_quiz(topic, num_questions, context=context)
        self.session.add_topic(topic)
        return questions

    # Function to record a quiz result in the student session
    def record_quiz_score(self, topic: str, score: int, total: int):
        self.session.add_quiz_result(topic, score, total)
