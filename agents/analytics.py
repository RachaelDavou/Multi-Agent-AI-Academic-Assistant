# Analytics Agent — tracks student performance and provides insights
from typing import Optional, Dict
from langchain_openai import ChatOpenAI

from utils.session import StudentSession


# Analytics agent class — analyzes session data and generates feedback
class AnalyticsAgent:

    name = "AnalyticsAgent"

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0.4)

    # Function to generate a natural-language analysis of the student's session
    def analyze(self, session: StudentSession) -> dict:
        summary = session.get_analytics_summary()

        # Return early if no data has been collected yet
        if not summary["quiz_results"] and not summary["topics_studied"]:
            return {
                "agent": self.name,
                "analysis": "No activity data yet. Start studying or take a quiz to see your analytics!",
                "summary": summary,
            }

        prompt = f"""You are a learning analytics expert. Analyze this student's session data
and provide encouraging, actionable feedback.

Student: {summary['student_name']}
Topics studied: {', '.join(summary['topics_studied']) or 'None yet'}
Quiz results: {summary['quiz_results']}
Average score: {summary['average_score']}%
Weak areas: {', '.join(summary['weak_areas']) or 'None identified'}
Session duration: {summary['session_duration_minutes']} minutes
Materials used: {', '.join(summary['selected_courses'] + summary['uploaded_files']) or 'None'}

Provide:
1. A brief performance summary (2-3 sentences)
2. Identified strengths
3. Areas needing improvement
4. 3 specific study recommendations
Keep the tone encouraging and constructive."""

        response = self.llm.invoke([("human", prompt)])
        return {
            "agent": self.name,
            "analysis": response.content,
            "summary": summary,
        }

    # Function to generate a personalized study plan based on weak areas
    def suggest_study_plan(self, weak_areas: list, available_hours: float) -> str:
        if not weak_areas:
            return "Great job! No weak areas identified. Keep up the consistent study habits."

        prompt = f"""Create a focused study plan for a student.
Weak areas: {', '.join(weak_areas)}
Available study time: {available_hours} hours

Produce a practical, hour-by-hour study plan that prioritizes weak areas.
Include specific activities (reading, practice problems, review)."""

        response = self.llm.invoke([("human", prompt)])
        return response.content

    # Function to return structured progress data for charts on the analytics dashboard
    def get_progress_data(self, session: StudentSession) -> Dict:
        summary = session.get_analytics_summary()
        return {
            "quiz_topics": [r["topic"] for r in summary["quiz_results"]],
            "quiz_scores": [r["percentage"] for r in summary["quiz_results"]],
            "topics_studied": summary["topics_studied"],
            "weak_areas": summary["weak_areas"],
            "average_score": summary["average_score"],
            "session_duration": summary["session_duration_minutes"],
        }
