# ============================================================
# app/models/intervention.py — Interventions table
# ============================================================
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, Text, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import enum


class InterventionType(str, enum.Enum):
    counseling = "Counseling"
    financial_support = "Financial Support"
    academic_support = "Academic Support"
    mentorship = "Mentorship"
    family_outreach = "Family Outreach"


class InterventionStatus(str, enum.Enum):
    pending = "Pending"
    active = "Active"
    completed = "Completed"


class InterventionOutcome(str, enum.Enum):
    improving = "Improving"
    stable = "Stable"
    improved = "Improved"
    declined = "Declined"
    none = "—"


class Intervention(Base):
    __tablename__ = "interventions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    type = Column(Enum(InterventionType), nullable=False)
    assigned_by = Column(String, nullable=False)              # Name of assigner
    assigned_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(InterventionStatus), default=InterventionStatus.pending)
    outcome = Column(Enum(InterventionOutcome), default=InterventionOutcome.none)
    initial_risk_score = Column(Float, nullable=True)
    final_risk_score = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    date_assigned = Column(DateTime(timezone=True), server_default=func.now())
    date_updated = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("Student", back_populates="interventions")
    timeline_events = relationship("TimelineEvent", back_populates="intervention", cascade="all, delete")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=False)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    event_type = Column(String, nullable=False)               # "Counseling Session", "AI Alert", etc.
    description = Column(Text, nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    intervention = relationship("Intervention", back_populates="timeline_events")
