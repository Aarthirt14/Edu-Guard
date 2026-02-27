# ============================================================
# app/api/routes/students.py
# GET  /api/students/high-risk          → all high-risk (admin/counselor)
# GET  /api/students/{id}               → student detail
# POST /api/students/                   → create student (admin)
# PUT  /api/students/{id}               → update student data
# GET  /api/students/{id}/history       → risk score history
# POST /api/students/predict            → ML risk prediction
# ============================================================
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.schemas.student import StudentOut, StudentCreate, StudentUpdate, PredictRequest, PredictResponse
from app.services.student_service import (get_high_risk_students, get_student_by_id,
                                           create_student, update_student, get_risk_history,
                                           get_risk_trend_factors)
from app.services.auth_service import get_current_user, require_role
from app.models.user import User, UserRole
from app.ml.model import predict_risk
from app.core.config import settings

router = APIRouter(prefix="/students", tags=["Students"])


@router.get("/high-risk", response_model=List[StudentOut], summary="Get all high-risk students")
def high_risk_students(
    class_filter: Optional[str] = Query(None, alias="class"),
    semester_filter: Optional[str] = Query(None, alias="semester"),
    factor_filter: Optional[str] = Query(None, alias="factor"),
    threshold: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns only students with risk_score >= threshold (default 70).
    Faculty sees only their own class. Admin/counselor see all.

    **Frontend usage (renderHighRiskTable in app.js):**
    ```js
    const res = await fetch('/api/students/high-risk', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    const students = await res.json();
    ```
    """
    t = threshold or settings.HIGH_RISK_THRESHOLD
    return get_high_risk_students(
        db, t,
        class_filter=class_filter,
        semester_filter=semester_filter,
        factor_filter=factor_filter,
        role=current_user.role,
        assigned_class=current_user.assigned_class,
    )


@router.get("/{student_id}", response_model=StudentOut, summary="Get student by ID")
def student_detail(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = get_student_by_id(db, student_id)
    # Students can only view themselves
    if current_user.role == UserRole.student and student.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")
    return student


@router.post("/", response_model=StudentOut, status_code=201, summary="Create a new student")
def create(
    data: StudentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return create_student(db, data)


@router.put("/{student_id}", response_model=StudentOut, summary="Update student data + re-run ML prediction")
def update(
    student_id: str,
    data: StudentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.faculty)),
):
    """
    Called when faculty uploads attendance/marks CSV.
    Re-runs ML model and updates risk_score + trend.
    """
    return update_student(db, student_id, data)


@router.get("/{student_id}/history", summary="Get risk score history for charts")
def risk_history(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns array of {risk_score, recorded_at} — used by the
    student dashboard attendance/marks trend charts.
    """
    history = get_risk_history(db, student_id)
    return [{"risk_score": h.risk_score, "recorded_at": h.recorded_at} for h in history]


@router.get("/{student_id}/risk-trend", summary="Get attendance/marks/fee trends driving risk")
def risk_trend(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = get_student_by_id(db, student_id)
    if current_user.role == UserRole.student and student.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")
    return get_risk_trend_factors(db, student_id)


@router.post("/predict", response_model=PredictResponse, summary="Run ML dropout risk prediction")
def predict(
    data: PredictRequest,
    _: User = Depends(get_current_user),
):
    """
    **Core ML endpoint.**
    Send student metrics → receive risk score (0-100), level, factors, and recommendation.

    **Frontend usage:**
    ```js
    const res = await fetch('/api/students/predict', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ attendance: 48, marks: 32, has_financial_issue: true })
    });
    const prediction = await res.json();
    // { risk_score: 87.4, risk_level: "high", recommendation: "..." }
    ```
    """
    result = predict_risk(
        attendance=data.attendance,
        marks=data.marks,
        has_financial_issue=data.has_financial_issue,
        has_family_issue=data.has_family_issue,
        semester=data.semester or 4,
    )
    return PredictResponse(**result)
