# ============================================================
# app/models/student.py — Students, WeeklyRecords, RiskHistory
# ============================================================
from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(String, primary_key=True, index=True)           # "STU-1024"
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True)
    class_name = Column(String, nullable=False)                  # "CS-A"
    semester = Column(String, nullable=False)                    # "Semester 4"

    # --- Legacy simple fields (kept for backward compat) ---
    attendance = Column(Float, default=100.0)
    marks = Column(Float, default=100.0)
    has_financial_issue = Column(Boolean, default=False)
    has_family_issue = Column(Boolean, default=False)

    # --- Static admission fields (Model 1 input) ---
    family_income = Column(Float, nullable=True)
    scholarship = Column(String, nullable=True)                 # "Yes" / "No"
    education_loan = Column(String, nullable=True)              # "Yes" / "No"
    father_occupation = Column(String, nullable=True)
    mother_occupation = Column(String, nullable=True)
    parent_education = Column(String, nullable=True)
    home_location = Column(String, nullable=True)               # "Rural" / "Urban"
    hs_grade = Column(Float, nullable=True)                     # HighSchool_Grade
    admission_quota = Column(String, nullable=True)             # "Merit" / "Management"

    # --- Risk scores ---
    baseline_risk_score = Column(Float, nullable=True)          # Model 1 — set once
    dynamic_risk_score = Column(Float, nullable=True)           # Model 2 — updated weekly
    risk_score = Column(Float, default=0.0)                     # Blended score
    risk_trend = Column(String, default="stable")               # "up" | "down" | "stable"
    weeks_tracked = Column(Integer, default=0)

    counselor_id = Column(String, ForeignKey("users.id"), nullable=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    counselor_rel = relationship("User", foreign_keys=[counselor_id], back_populates="students")
    interventions = relationship("Intervention", back_populates="student", cascade="all, delete")
    risk_history = relationship("RiskHistory", back_populates="student", cascade="all, delete")
    weekly_records = relationship("WeeklyRecord", back_populates="student", cascade="all, delete",
                                  order_by="WeeklyRecord.week_number")

    @property
    def risk_factors(self):
        """Derive factors dynamically from data."""
        factors = []
        if self.has_financial_issue or (self.family_income and self.family_income < 20000):
            factors.append("financial")
        if self.attendance < 60:
            factors.append("attendance")
        if self.marks < 40:
            factors.append("academic")
        if self.has_family_issue:
            factors.append("family")
        return factors


class WeeklyRecord(Base):
    """Raw weekly data uploaded by faculty. 7 columns only."""
    __tablename__ = "weekly_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False, index=True)
    week_number = Column(Integer, nullable=False)
    attendance_pct = Column(Float, nullable=False)              # 0–100
    ia_marks = Column(Float, nullable=True)                     # NULL if not yet available
    semester_marks = Column(Float, nullable=True)               # NULL if not yet available
    backlog_count = Column(Integer, nullable=True)              # NULL → treated as 0
    fee_outstanding = Column(Boolean, default=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="weekly_records")


class RiskHistory(Base):
    __tablename__ = "risk_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    risk_score = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student", back_populates="risk_history")
