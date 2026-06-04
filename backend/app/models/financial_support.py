from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class FinancialSupportCase(Base):
    __tablename__ = "financial_support_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intervention_id = Column(Integer, ForeignKey("interventions.id"), nullable=False, unique=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)

    status = Column(String, nullable=False, default="Awaiting Student Input")

    fee_outstanding_amount = Column(Float, nullable=True)
    scholarship_eligibility = Column(String, nullable=True)
    social_category = Column(String, nullable=True)
    parent_occupation = Column(String, nullable=True)
    family_income_band = Column(String, nullable=True)
    scholarship_applied = Column(String, nullable=True)
    preferred_support_type = Column(String, nullable=True)
    student_notes = Column(Text, nullable=True)

    ai_summary = Column(Text, nullable=True)
    ai_recommendations = Column(JSON, nullable=True)

    admin_plan_type = Column(String, nullable=True)
    admin_plan = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student = relationship("Student")
    intervention = relationship("Intervention")
