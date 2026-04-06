# Tutor Agent — answers academic questions using RAG over loaded documents
import random
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough


# Prompt template used when course materials are loaded
TUTOR_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are an expert academic tutor. Use the provided context from course materials
to give a clear, educational answer. If the context doesn't cover the question, use your general
knowledge but mention that the answer isn't from the loaded materials.

Context from course materials:
{context}

Student question: {question}

Provide a structured, easy-to-understand explanation. Use examples where helpful.
If relevant, suggest follow-up topics the student could explore.

IMPORTANT — Math formatting rules:
- Inline math: wrap in single dollar signs, e.g. $\\mu = \\frac{{\\Sigma x}}{{n}}$
- Display/block math (its own line): wrap in double dollar signs, e.g. $$\\mu = \\frac{{\\Sigma x}}{{n}}$$
- Never use [ ] or \\[ \\] or ( ) as math delimiters.""",
)


# Function to join retrieved document chunks into a single string
def _format_docs(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


# Pydantic schema for a single quiz question — used with structured output so the
# LLM never assigns option letters (that is done in code after shuffling).
class _QuizQuestion(BaseModel):
    question: str = Field(description="The quiz question text")
    correct: str = Field(description="The one factually correct answer")
    distractors: List[str] = Field(description="Exactly three plausible but incorrect answers")


class _QuizOutput(BaseModel):
    questions: List[_QuizQuestion]


# Tutor agent class — handles academic tutoring with optional RAG
class TutorAgent:

    name = "TutorAgent"

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
        self._chain = None
        self._retriever = None

    # Function to attach a LangChain retriever from the catalogue or upload store
    def set_retriever(self, retriever):
        self._retriever = retriever
        self._chain = (
            {
                "context": retriever | _format_docs,
                "question": RunnablePassthrough(),
            }
            | TUTOR_PROMPT
            | self.llm
            | StrOutputParser()
        )

    # Function to answer a question using RAG or general knowledge as fallback
    def answer(self, question: str, web_context: str = "") -> dict:
        web_section = (
            f"\n\nAdditional context from a live web search:\n{web_context}"
            if web_context else ""
        )

        if self._chain and self._retriever:
            answer_text = self._chain.invoke(question + web_section)
            source_docs = self._retriever.invoke(question)
            sources = list({
                doc.metadata.get("source", "Unknown") for doc in source_docs
            })
            if web_context:
                sources.append("🌐 Web")
            return {
                "agent": self.name,
                "answer": answer_text,
                "sources": sources,
                "used_rag": True,
            }
        else:
            # No documents loaded — answer from general knowledge
            system = (
                "You are an expert academic tutor. Answer clearly and educationally. "
                "For math, use $...$ for inline and $$...$$ for display equations. "
                "Never use [ ] or \\[ \\] as math delimiters."
            )
            human = question + web_section
            response = self.llm.invoke([("system", system), ("human", human)])
            sources = ["🌐 Web"] if web_context else []
            return {
                "agent": self.name,
                "answer": response.content,
                "sources": sources,
                "used_rag": False,
            }

    # Function to summarize a piece of text — truncates very long inputs to avoid token limits
    def summarize(self, text: str) -> str:
        # Keep roughly 12000 characters (~3000 tokens) to stay within context limits
        MAX_CHARS = 12000
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS] + "\n\n[Note: text was truncated to fit within summarization limits.]"
        messages = [
            ("system", (
                "You are an academic tutor. Provide a clear, well-structured summary with: "
                "a brief overview, key concepts or main points, and any important conclusions. "
                "Use headers to organize the output."
            )),
            ("human", f"Please summarize the following:\n\n{text}"),
        ]
        response = self.llm.invoke(messages)
        return response.content

    # Function to generate multiple-choice quiz questions on a topic.
    # Function to generate quiz questions using structured output.
    # The LLM returns JSON with 'correct' and 'distractors' as plain text — it never
    # assigns option letters. Letters are assigned here after shuffling, guaranteeing
    # that grading is always accurate regardless of LLM behaviour.
    def generate_quiz(self, topic: str, num_questions: int = 3, context: str = "") -> List[dict]:
        structured_llm = ChatOpenAI(
            model=self.llm.model_name, temperature=0.8
        ).with_structured_output(_QuizOutput)

        context_block = (
            f"\n\nBase your questions on this course material:\n{context}"
            if context else ""
        )

        messages = [
            ("system", (
                "You are an academic tutor. Generate factually accurate quiz questions. "
                "For math use $...$ for inline and $$...$$ for display equations."
            )),
            (
                "human",
                f"Generate {num_questions} multiple-choice questions about: {topic}.{context_block}\n\n"
                "Each question must have exactly one correct answer and exactly three wrong distractors. "
                "Make sure 'correct' is undeniably the right answer and the distractors are clearly wrong. "
                "Vary difficulty and phrasing across questions."
            ),
        ]

        result = structured_llm.invoke(messages)

        # Shuffle options and assign A/B/C/D in code — LLM never picks a letter
        questions = []
        for q in result.questions:
            all_options = [q.correct] + q.distractors[:3]
            random.shuffle(all_options)
            letters = ["A", "B", "C", "D"]
            options = {letters[i]: all_options[i] for i in range(len(all_options))}
            answer = next(letter for letter, text in options.items() if text == q.correct)
            questions.append({"question": q.question, "options": options, "answer": answer})

        random.shuffle(questions)
        return questions
