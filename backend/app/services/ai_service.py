"""
app/services/ai_service.py — AI Assistant using Anthropic Claude
"""
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.student import Student
from app.models.intervention import Intervention

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def build_system_context(db: Session) -> str:
    """Builds a context string from live DB data to inject into the AI prompt."""
    students = db.query(Student).filter(Student.risk_score >= 70).order_by(
        Student.risk_score.desc()
    ).limit(10).all()
    interventions = db.query(Intervention).filter(
        Intervention.status == "Active"
    ).count()

    student_summary = "\n".join(
        f"  - {s.name} ({s.student_code}): Risk={s.risk_score:.0f}, "
        f"Class={s.student_class}, Attendance={s.attendance_pct:.0f}%, "
        f"Factors={','.join(s.risk_factors or [])}, Status={s.intervention_status}"
        for s in students
    )
    return f"""You are EduGuard AI Assistant, an expert student dropout prevention advisor.
You have access to real-time data from the EduGuard system.

Current High-Risk Students (top 10 by score):
{student_summary}

Active Interventions: {interventions}

Your role:
- Help identify students who need immediate attention
- Suggest evidence-based intervention strategies
- Explain risk score factors clearly
- Provide data-driven recommendations
- Be concise, professional, and actionable
- Focus ONLY on high-risk students (score >= 70)
"""


def chat(message: str, db: Session) -> str:
    """Sends a message to Claude with live DB context and returns the response."""
    if not settings.ANTHROPIC_API_KEY:
        # Fallback if no API key configured
        return (
            "AI Assistant is not configured. "
            "Please set ANTHROPIC_API_KEY in your .env file to enable live AI responses."
        )
    try:
        client = _get_client()
        system = build_system_context(db)
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            system=system,
            messages=[{"role": "user", "content": message}],
        )
        return response.content[0].text
    except Exception as e:
        return f"AI service error: {str(e)}"
