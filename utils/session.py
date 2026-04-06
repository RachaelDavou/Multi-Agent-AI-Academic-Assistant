# Session state management for tracking student analytics
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# Stores the result of a single quiz attempt
@dataclass
class QuizResult:
    topic: str
    score: int
    total: int
    timestamp: float = field(default_factory=time.time)

    @property
    def percentage(self) -> float:
        return round((self.score / self.total) * 100, 1) if self.total else 0.0


# Stores a single chat message with role and optional agent name
@dataclass
class ChatMessage:
    role: str  # "user" | "assistant" | "agent"
    content: str
    agent_name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


# Tracks everything about a student's current session
class StudentSession:

    def __init__(self, student_name: str = "Student"):
        self.student_name = student_name
        self.messages: List[ChatMessage] = []
        self.quiz_results: List[QuizResult] = []
        self.topics_studied: List[str] = []
        self.uploaded_files: List[str] = []
        self.selected_courses: List[str] = []
        self.weak_areas: List[str] = []
        self.start_time: float = time.time()

    # Function to add a chat message to the session history
    def add_message(self, role: str, content: str, agent_name: Optional[str] = None):
        self.messages.append(ChatMessage(role=role, content=content, agent_name=agent_name))

    # Function to record a quiz result and flag weak areas (below 60%)
    def add_quiz_result(self, topic: str, score: int, total: int):
        self.quiz_results.append(QuizResult(topic=topic, score=score, total=total))
        if score / total < 0.6 and topic not in self.weak_areas:
            self.weak_areas.append(topic)

    # Function to add a topic to the studied list (no duplicates)
    def add_topic(self, topic: str):
        if topic not in self.topics_studied:
            self.topics_studied.append(topic)

    # Function to return a summary dict used by the analytics agent and dashboard
    def get_analytics_summary(self) -> Dict:
        avg_score = (
            sum(r.percentage for r in self.quiz_results) / len(self.quiz_results)
            if self.quiz_results else 0.0
        )
        return {
            "student_name": self.student_name,
            "topics_studied": self.topics_studied,
            "quiz_results": [
                {"topic": r.topic, "score": r.score, "total": r.total, "percentage": r.percentage}
                for r in self.quiz_results
            ],
            "average_score": round(avg_score, 1),
            "weak_areas": self.weak_areas,
            "uploaded_files": self.uploaded_files,
            "selected_courses": self.selected_courses,
            "session_duration_minutes": round((time.time() - self.start_time) / 60, 1),
            "total_messages": len(self.messages),
        }
