"""System settings endpoints (admin only)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.auth_service import require_role
from app.models.user import User, UserRole
from app.models.settings import SystemSettings
from app.schemas.settings import ThresholdUpdate, NotificationUpdate, SettingsOut

router = APIRouter(prefix="/settings", tags=["Settings"])


def _get_or_create(db: Session) -> SystemSettings:
    s = db.query(SystemSettings).filter(SystemSettings.id == 1).first()
    if not s:
        s = SystemSettings(id=1)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.get("/", response_model=SettingsOut, summary="Get current system settings")
def get_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return _get_or_create(db)


@router.put("/thresholds", response_model=SettingsOut, summary="Update risk score thresholds")
def update_thresholds(
    data: ThresholdUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    s = _get_or_create(db)
    s.high_risk_threshold = data.high_risk_threshold
    s.attendance_alert_threshold = data.attendance_alert_threshold
    s.marks_drop_alert_percentage = data.marks_drop_alert_percentage
    db.commit()
    db.refresh(s)
    return s


@router.put("/notifications", response_model=SettingsOut, summary="Update notification preferences")
def update_notifications(
    data: NotificationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    s = _get_or_create(db)
    s.email_notifications = data.email_notifications
    s.sms_alerts = data.sms_alerts
    s.ai_auto_suggestions = data.ai_auto_suggestions
    db.commit()
    db.refresh(s)
    return s
