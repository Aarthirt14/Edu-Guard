"""
app/schemas/settings.py — System settings schemas
"""
from pydantic import BaseModel


class ThresholdUpdate(BaseModel):
    high_risk_threshold: int
    attendance_alert_threshold: int
    marks_drop_alert_percentage: int


class NotificationUpdate(BaseModel):
    email_notifications: bool
    sms_alerts: bool
    ai_auto_suggestions: bool


class SettingsOut(BaseModel):
    high_risk_threshold: int
    attendance_alert_threshold: int
    marks_drop_alert_percentage: int
    email_notifications: bool
    sms_alerts: bool
    ai_auto_suggestions: bool

    class Config:
        from_attributes = True
