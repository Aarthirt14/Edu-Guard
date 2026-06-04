from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.student import Student
from app.models.user import User
from app.schemas.counseling import CounselingSessionCreate, CounselingSessionOut, CounselingSessionComplete, CounselingStats
from app.services.auth_service import get_current_user
from app.services.counseling_service import schedule_counseling_session, list_sessions_for_user, complete_session

router = APIRouter(prefix="/counseling", tags=["Counseling"])


@router.get("/sessions/me", response_model=List[CounselingSessionOut], summary="List counseling sessions for current user")
def my_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = list_sessions_for_user(db, current_user)
    result: list[CounselingSessionOut] = []
    for row in rows:
        out = CounselingSessionOut.model_validate(row)
        student = db.query(Student).filter(Student.id == row.student_id).first()
        out.student_name = student.name if student else None
        out.class_name = student.class_name if student else None
        result.append(out)
    return result


@router.post("/sessions", response_model=CounselingSessionOut, summary="Schedule counseling session")
def create_session(
    payload: CounselingSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = schedule_counseling_session(db, payload, current_user)
    out = CounselingSessionOut.model_validate(row)
    student = db.query(Student).filter(Student.id == row.student_id).first()
    out.student_name = student.name if student else None
    out.class_name = student.class_name if student else None
    return out


@router.put("/sessions/{session_id}/complete", response_model=CounselingSessionOut, summary="Mark counseling session completed")
def mark_completed(
    session_id: int,
    payload: CounselingSessionComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = complete_session(db, session_id, payload, current_user)
    out = CounselingSessionOut.model_validate(row)
    student = db.query(Student).filter(Student.id == row.student_id).first()
    out.student_name = student.name if student else None
    out.class_name = student.class_name if student else None
    return out


@router.get("/sessions/stats/me", response_model=CounselingStats, summary="Counseling active/completed counts for current user")
def my_session_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = list_sessions_for_user(db, current_user)
    active = len([r for r in rows if (r.status or "").lower() == "active"])
    completed = len([r for r in rows if (r.status or "").lower() == "completed"])
    return CounselingStats(active=active, completed=completed)
