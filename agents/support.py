# Support Agent — handles student wellbeing, motivation, and study planning
from typing import Optional
from langchain_openai import ChatOpenAI


# System prompt that defines the support agent's tone and scope
SUPPORT_SYSTEM_PROMPT = """You are a warm, empathetic student support advisor at a university.
You help students with:
- Study strategies and time management
- Motivation and dealing with academic stress
- Exam preparation tips
- Goal setting and academic planning
- General wellbeing advice

Always be encouraging, practical, and supportive. If a student seems distressed,
acknowledge their feelings before offering advice."""


# Support agent class — handles non-academic student requests
class SupportAgent:

    name = "SupportAgent"

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.6)

    # Function to respond to a student support request
    def respond(self, message: str, context: str = "") -> dict:
        messages = [("system", SUPPORT_SYSTEM_PROMPT)]
        if context:
            messages.append(("system", f"Student context: {context}"))
        messages.append(("human", message))

        response = self.llm.invoke(messages)
        return {
            "agent": self.name,
            "answer": response.content,
        }

    # Function to return study tips tailored to a specific subject
    def get_study_tips(self, subject: str) -> str:
        messages = [
            ("system", SUPPORT_SYSTEM_PROMPT),
            ("human", f"Give me 5 practical study tips specifically for {subject}."),
        ]
        response = self.llm.invoke(messages)
        return response.content

    # Function to provide motivational support for a specific situation
    def motivate(self, situation: str) -> str:
        messages = [
            ("system", SUPPORT_SYSTEM_PROMPT),
            ("human", f"I need motivation. Here's my situation: {situation}"),
        ]
        response = self.llm.invoke(messages)
        return response.content
