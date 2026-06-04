from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func

from app.db.database import Base


class CounselingSession(Base):
    __tablename__ = "counseling_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=True)
    counselor_id = Column(String, ForeignKey("users.id"), nullable=True)
    counselor_name = Column(String, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False, default="Active")
    message_to_student = Column(Text, nullable=True)
    message_to_faculty = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    completion_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
