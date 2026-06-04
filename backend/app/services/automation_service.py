import logging
import httpx
from typing import Any, Dict, Optional

from app.core.config import settings
from app.models.student import Student

logger = logging.getLogger(__name__)

async def send_to_n8n(payload: Dict[str, Any]) -> bool:
    """
    Sends the action ticket payload to the configured n8n webhook.
    """
    if not settings.N8N_WEBHOOK_URL:
        logger.warning("⚠️ N8N_WEBHOOK_URL not configured. Skipping automation.")
        return False

    headers = {}
    if settings.N8N_API_KEY:
        headers["X-API-KEY"] = settings.N8N_API_KEY

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.N8N_WEBHOOK_URL,
                json=payload,
                headers=headers
            )
            
            if response.is_success:
                logger.info(f"✅ Successfully sent automation payload to n8n for student {payload.get('student_id')}")
                return True
            else:
                logger.error(f"❌ n8n webhook failed with status {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error sending to n8n: {str(e)}")
        return False


def build_intervention_payload(student: Student, action_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs the standardized JSON payload for n8n.
    """
    return {
        "student_id": student.id,
        "student_name": student.name,
        "class_name": student.class_name,
        "risk_score": round(float(student.risk_score or 0), 1),
        "risk_level": "high" if (student.risk_score or 0) >= settings.HIGH_RISK_THRESHOLD else "moderate",
        "priority": action_data.get("priority", "Medium"),
        "reason_summary": action_row_to_summary(action_data),
        "recommended_intervention": action_data.get("recommended_intervention", "Counseling"),
        "risk_trend": student.risk_trend or "stable",
        "factors": action_data.get("factors") or [],
        "source": "eduguard-action-engine"
    }


def action_row_to_summary(row: Dict[str, Any]) -> str:
    """Helper to ensure we have a clean reason string."""
    reason = str(row.get("reason_summary") or "")
    if not reason:
        factors = row.get("factors") or []
        reason = f"Flagged due to high risk score and factors: {', '.join(factors)}"
    return reason
