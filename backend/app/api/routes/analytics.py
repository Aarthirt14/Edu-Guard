# ============================================================
# app/api/routes/analytics.py
# GET  /api/analytics/dashboard   → stat cards
# GET  /api/analytics/            → charts data
# POST /api/analytics/ai-chat     → AI assistant
# ============================================================
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.analytics import DashboardStats, AnalyticsResponse, AIChatRequest, AIChatResponse
from app.services.analytics_service import get_dashboard_stats, get_analytics, ai_chat
from app.services.auth_service import get_current_user, require_role
from app.models.user import User, UserRole
from app.core.config import settings

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardStats, summary="Admin dashboard stat cards")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.counselor)),
):
    """
    Returns the 4 top stat cards:
    - High Risk Students
    - New High Risk This Week
    - Active Interventions
    - Improved After Intervention
    """
    return get_dashboard_stats(db, settings.HIGH_RISK_THRESHOLD)


@router.get("/", response_model=AnalyticsResponse, summary="Chart data for Analytics page")
def analytics(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    """Returns data for all 3 charts: risk trend, intervention success, factor distribution."""
    return get_analytics(db, settings.HIGH_RISK_THRESHOLD)


@router.post("/ai-chat", response_model=AIChatResponse, summary="AI assistant endpoint")
async def chat(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Powers the floating AI chat panel.
    Uses Anthropic Claude if ANTHROPIC_API_KEY is set,
    otherwise returns intelligent rule-based responses.

    **Frontend usage (sendAIMessage in app.js):**
    ```js
    const res = await fetch('/api/analytics/ai-chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ message: userInput })
    });
    const { reply } = await res.json();
    ```
    """
    reply = await ai_chat(payload.message, db)
    return AIChatResponse(reply=reply)
