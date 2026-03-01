from typing import Tuple

from app.models.intervention import Intervention
from app.models.student import Student
from app.services.student_service import get_risk_trend_factors


def generate_academic_support_note(db, student: Student, intervention: Intervention) -> Tuple[str, str]:
    try:
        trend = get_risk_trend_factors(db, student.id)
        drivers = trend.get("drivers") or []
        attendance = float(student.attendance or 0)
        marks = float(student.marks or 0)
        risk_score = float(student.risk_score or 0)
        trend_value = (student.risk_trend or "stable").lower()
        factors = [str(f).lower() for f in (student.risk_factors or [])]

        actions = []
        if marks < 45 or "academic" in factors:
            actions.append("Run subject-wise remediation this week and conduct a 10-mark checkpoint test in 7 days")
        if attendance < 75 or "attendance" in factors:
            actions.append("Start attendance recovery with daily class check-in and end-of-week parent update")
        if risk_score >= 85 or trend_value == "up":
            actions.append("Schedule one-to-one mentoring within 48 hours and review progress in the next weekly meeting")
        if "financial" in factors:
            actions.append("Coordinate with admin on fee-support follow-up so academics are not disrupted")

        if not actions:
            actions.append("Maintain weekly academic monitoring and assignment completion tracking")

        def as_sentence(text: str) -> str:
            value = " ".join(str(text or "").split()).strip().rstrip(".")
            return f"{value}." if value else ""

        status_value = intervention.status.value if intervention.status else "Pending"
        action_block = " ".join(as_sentence(item) for item in actions if str(item or "").strip())
        status_block = as_sentence(f"Current status: {status_value}")
        driver_block = as_sentence(f"Key driver: {drivers[0]}") if drivers else ""
        note = " ".join(part for part in [action_block, status_block, driver_block] if part).strip()
        return note, "rule-based"
    except Exception:
        return (
            "Rule-based plan unavailable right now. Please refresh.",
            "rule-based",
        )
