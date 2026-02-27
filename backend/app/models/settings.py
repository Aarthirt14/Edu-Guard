"""
app/models/settings.py — System Settings ORM model (singleton row)
"""
from sqlalchemy import Column, Integer, Boolean
from app.db.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, default=1)
    high_risk_threshold = Column(Integer, default=70)
    attendance_alert_threshold = Column(Integer, default=60)
    marks_drop_alert_percentage = Column(Integer, default=20)
    email_notifications = Column(Boolean, default=True)
    sms_alerts = Column(Boolean, default=True)
    ai_auto_suggestions = Column(Boolean, default=True)
