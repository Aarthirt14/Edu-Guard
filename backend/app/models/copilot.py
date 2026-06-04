from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CopilotRun(Base):
    __tablename__ = "copilot_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_type = Column(String, nullable=False, default="weekly")
    status = Column(String, nullable=False, default="completed")
    total_students_scanned = Column(Integer, nullable=False, default=0)
    high_risk_identified = Column(Integer, nullable=False, default=0)
    actions_created = Column(Integer, nullable=False, default=0)
    summary = Column(JSON, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    tickets = relationship("CopilotActionTicket", back_populates="run", cascade="all, delete")


class CopilotActionTicket(Base):
    __tablename__ = "copilot_action_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("copilot_runs.id"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    student_name = Column(String, nullable=True)
    class_name = Column(String, nullable=True)
    risk_score = Column(Float, nullable=False)
    risk_trend = Column(String, nullable=True)
    reason_summary = Column(Text, nullable=False)
    recommended_intervention = Column(String, nullable=False)
    priority = Column(String, nullable=False, default="Medium")
    n8n_status = Column(String, nullable=False, default="not_configured")
    n8n_reference = Column(String, nullable=True)
    status = Column(String, nullable=False, default="Open")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("CopilotRun", back_populates="tickets")
