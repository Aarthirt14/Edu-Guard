# ============================================================
# app/services/analytics_service.py — Analytics + AI Chat
# ============================================================
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional
from datetime import datetime, timedelta
import httpx, logging

from app.models.student import Student, RiskHistory
from app.models.intervention import Intervention, InterventionOutcome, InterventionStatus
from app.schemas.analytics import (DashboardStats, AnalyticsResponse, RiskTrendPoint,
                                   FactorDistribution, InterventionSuccessBreakdown)
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_dashboard_stats(db: Session, threshold: int = 70) -> DashboardStats:
    high_risk = db.query(Student).filter(Student.risk_score >= threshold).count()

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    new_this_week = db.query(RiskHistory).filter(
        RiskHistory.risk_score >= threshold,
        RiskHistory.recorded_at >= one_week_ago
    ).distinct(RiskHistory.student_id).count()

    active_ivs = db.query(Intervention).filter(
        Intervention.status == InterventionStatus.active
    ).count()

    improved = db.query(Intervention).filter(
        Intervention.outcome.in_([InterventionOutcome.improved, InterventionOutcome.improving])
    ).count()

    return DashboardStats(
        total_high_risk=high_risk,
        new_high_risk_this_week=new_this_week,
        active_interventions=active_ivs,
        improved_after_intervention=improved,
    )


def get_analytics(db: Session, threshold: int = 70) -> AnalyticsResponse:
    # Risk trend: last 6 months
    months = []
    for i in range(5, -1, -1):
        dt = datetime.utcnow() - timedelta(days=30 * i)
        label = dt.strftime("%b")
        count = db.query(RiskHistory).filter(
            RiskHistory.risk_score >= threshold,
            extract("month", RiskHistory.recorded_at) == dt.month,
            extract("year", RiskHistory.recorded_at) == dt.year,
        ).count()
        months.append(RiskTrendPoint(month=label, count=count))

    # Factor distribution
    students = db.query(Student).filter(Student.risk_score >= threshold).all()
    fin = sum(1 for s in students if s.has_financial_issue)
    att = sum(1 for s in students if s.attendance < 60)
    acad = sum(1 for s in students if s.marks < 40)
    fam = sum(1 for s in students if s.has_family_issue)

    # Intervention outcomes
    improved = db.query(Intervention).filter(Intervention.outcome == InterventionOutcome.improved).count()
    improving = db.query(Intervention).filter(Intervention.outcome == InterventionOutcome.improving).count()
    stable = db.query(Intervention).filter(Intervention.outcome == InterventionOutcome.stable).count()
    declined = db.query(Intervention).filter(Intervention.outcome == InterventionOutcome.declined).count()
    total_ivs = db.query(Intervention).count()
    no_change = max(0, total_ivs - improved - improving - stable - declined)

    return AnalyticsResponse(
        risk_trend=months,
        factor_distribution=FactorDistribution(financial=fin, attendance=att, academic=acad, family=fam),
        intervention_success=InterventionSuccessBreakdown(
            improved=improved + improving,
            stable=stable,
            no_change=no_change,
            declined=declined,
        ),
    )


async def ai_chat(message: str, db: Session) -> str:
    """
    Calls Anthropic Claude API with live DB context.
    Falls back to rule-based responses if no API key.
    """
    # Build context from live data
    high_risk = db.query(Student).filter(Student.risk_score >= 70).order_by(Student.risk_score.desc()).limit(5).all()
    no_intervention = db.query(Student).filter(Student.risk_score >= 70).all()
    active_count = db.query(Intervention).filter(Intervention.status == InterventionStatus.active).count()

    context = f"""You are EduGuard AI, an assistant for a student dropout prevention system.

Current system data:
- Total high-risk students: {len(high_risk)} shown (top 5 by score)
- Active interventions: {active_count}
- Top high-risk students: {", ".join(f"{s.name} (score: {s.risk_score:.0f}, factors: {s.risk_factors})" for s in high_risk)}

Answer concisely and factually. Focus on actionable advice for counselors and admins."""

    if not settings.ANTHROPIC_API_KEY:
        # Fallback rule-based responses
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["who", "which", "student", "list"]):
            names = ", ".join(f"{s.name} ({s.risk_score:.0f})" for s in high_risk)
            return f"Top high-risk students right now: <strong>{names}</strong>. All have risk scores above 70."
        if any(w in msg_lower for w in ["intervention", "assign", "action"]):
            return f"There are currently <strong>{active_count} active interventions</strong>. I recommend prioritising students with 3+ risk factors and no assigned intervention."
        if any(w in msg_lower for w in ["factor", "cause", "why"]):
            return "The primary dropout risk factors are: <strong>attendance below 60%</strong> (most common), followed by financial stress, academic decline, and family issues."
        return f"Based on current data, I'm tracking <strong>{len(no_intervention)} high-risk students</strong>. {active_count} have active interventions. Would you like details on a specific student or factor?"

    # Real Anthropic call
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 300,
                    "system": context,
                    "messages": [{"role": "user", "content": message}],
                },
            )
            data = response.json()
            return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return "AI assistant is temporarily unavailable. Please try again shortly."
