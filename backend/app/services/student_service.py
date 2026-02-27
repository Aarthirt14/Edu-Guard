# ============================================================
# app/services/student_service.py — Student Business Logic
# ============================================================
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional
from app.models.student import Student, RiskHistory, WeeklyRecord
from app.models.user import UserRole
from app.schemas.student import StudentCreate, StudentUpdate
from app.ml.model import predict_risk
import logging

logger = logging.getLogger(__name__)


def get_high_risk_students(
    db: Session,
    threshold: int = 70,
    class_filter: Optional[str] = None,
    semester_filter: Optional[str] = None,
    factor_filter: Optional[str] = None,
    role: Optional[UserRole] = None,
    assigned_class: Optional[str] = None,
) -> List[Student]:
    query = db.query(Student).filter(Student.risk_score >= threshold)

    # Faculty sees only their class
    if role == UserRole.faculty and assigned_class:
        query = query.filter(Student.class_name == assigned_class)
    elif class_filter:
        query = query.filter(Student.class_name == class_filter)

    if semester_filter:
        query = query.filter(Student.semester == semester_filter)

    students = query.order_by(Student.risk_score.desc()).all()

    # Factor filter (post-query, since factors are derived)
    if factor_filter:
        students = [s for s in students if factor_filter in s.risk_factors]

    return students


def get_student_by_id(db: Session, student_id: str) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Student '{student_id}' not found")
    return student


def create_student(db: Session, data: StudentCreate) -> Student:
    existing = db.query(Student).filter(Student.id == data.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Student ID '{data.id}' already exists")

    sem_num = int(data.semester.split()[-1]) if "Semester" in data.semester else 4
    pred = predict_risk(data.attendance, data.marks,
                        data.has_financial_issue, data.has_family_issue, sem_num)

    student = Student(
        **data.model_dump(),
        risk_score=pred["risk_score"],
        risk_trend="up" if pred["risk_score"] >= 70 else "stable",
    )
    db.add(student)
    db.add(RiskHistory(student_id=data.id, risk_score=pred["risk_score"]))
    db.commit()
    db.refresh(student)
    return student


def update_student(db: Session, student_id: str, data: StudentUpdate) -> Student:
    student = get_student_by_id(db, student_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(student, field, value)

    # Re-run prediction after update
    sem_num = int(student.semester.split()[-1]) if "Semester" in student.semester else 4
    pred = predict_risk(student.attendance, student.marks,
                        student.has_financial_issue, student.has_family_issue, sem_num)

    old_score = student.risk_score
    student.risk_score = pred["risk_score"]
    student.risk_trend = "up" if pred["risk_score"] > old_score else "down"

    db.add(RiskHistory(student_id=student_id, risk_score=pred["risk_score"]))
    db.commit()
    db.refresh(student)
    return student


def get_risk_history(db: Session, student_id: str) -> List[RiskHistory]:
    get_student_by_id(db, student_id)
    return (db.query(RiskHistory)
              .filter(RiskHistory.student_id == student_id)
              .order_by(RiskHistory.recorded_at.asc())
              .all())


def get_risk_trend_factors(db: Session, student_id: str) -> dict:
    student = get_student_by_id(db, student_id)
    records = (db.query(WeeklyRecord)
               .filter(WeeklyRecord.student_id == student_id)
               .order_by(WeeklyRecord.week_number.asc())
               .all())

    attendance_series = []
    marks_series = []
    fee_series = []

    for record in records:
        attendance_series.append({"week": record.week_number, "value": float(record.attendance_pct)})
        marks_series.append({"week": record.week_number, "value": float(record.ia_marks) if record.ia_marks is not None else None})
        fee_series.append({"week": record.week_number, "value": 1 if record.fee_outstanding else 0})

    def _trend(points, positive_is_good=True):
        vals = [p["value"] for p in points if p["value"] is not None]
        if len(vals) < 2:
            return "stable"
        delta = vals[-1] - vals[0]
        if abs(delta) < 0.5:
            return "stable"
        if positive_is_good:
            return "improving" if delta > 0 else "declining"
        return "declining" if delta > 0 else "improving"

    attendance_trend = _trend(attendance_series, positive_is_good=True)
    marks_trend = _trend(marks_series, positive_is_good=True)
    fee_trend = _trend(fee_series, positive_is_good=False)

    drivers = []
    if attendance_series:
        first_att = attendance_series[0]["value"]
        latest_att = attendance_series[-1]["value"]
        if latest_att < first_att:
            drivers.append(f"Attendance dropped from {first_att:.0f}% to {latest_att:.0f}%.")
        elif latest_att > first_att:
            drivers.append(f"Attendance improved from {first_att:.0f}% to {latest_att:.0f}%.")

    marks_values = [p for p in marks_series if p["value"] is not None]
    if marks_values:
        first_marks = marks_values[0]["value"]
        latest_marks = marks_values[-1]["value"]
        if latest_marks < first_marks:
            drivers.append(f"IA marks declined from {first_marks:.0f} to {latest_marks:.0f}.")
        elif latest_marks > first_marks:
            drivers.append(f"IA marks improved from {first_marks:.0f} to {latest_marks:.0f}.")

    if fee_series:
        fee_flags = [p["value"] for p in fee_series]
        if fee_flags[-1] == 1:
            drivers.append("Fee is currently outstanding.")
        elif any(fee_flags):
            drivers.append("Fee was previously outstanding but is now cleared.")

    if not drivers:
        drivers.append("No significant weekly trend drivers detected yet.")

    return {
        "student_id": student.id,
        "student_name": student.name,
        "risk_score": float(student.risk_score or 0),
        "attendance_trend": attendance_trend,
        "marks_trend": marks_trend,
        "fee_trend": fee_trend,
        "attendance_points": attendance_series,
        "marks_points": marks_series,
        "fee_points": fee_series,
        "drivers": drivers,
    }
