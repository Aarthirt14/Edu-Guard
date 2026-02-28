from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.counseling_session import CounselingSession
from app.models.intervention import Intervention, InterventionType, InterventionStatus, InterventionOutcome, TimelineEvent
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.counseling import CounselingSessionCreate, CounselingSessionComplete


def _resolve_student_for_user(db: Session, current_user: User) -> Student:
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        student = db.query(Student).filter(Student.email == current_user.email).first()
    if not student and current_user.id.startswith("STU-"):
        student = db.query(Student).filter(Student.id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=404, detail="No linked student profile found")
    return student


def schedule_counseling_session(db: Session, payload: CounselingSessionCreate, current_user: User) -> CounselingSession:
    if current_user.role not in (UserRole.counselor, UserRole.admin):
        raise HTTPException(status_code=403, detail="Only counselor/admin can schedule sessions")

    student = db.query(Student).filter(Student.id == payload.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    intervention = Intervention(
        student_id=payload.student_id,
        type=InterventionType.counseling,
        assigned_by=current_user.name,
        assigned_by_id=current_user.id,
        status=InterventionStatus.active,
        outcome=InterventionOutcome.none,
        notes=payload.notes,
    )
    db.add(intervention)
    db.flush()

    db.add(TimelineEvent(
        intervention_id=intervention.id,
        student_id=payload.student_id,
        event_type="Counseling Scheduled",
        description=f"Counseling session scheduled by {current_user.name} for {payload.scheduled_at.isoformat()}.",
    ))

    session = CounselingSession(
        student_id=payload.student_id,
        intervention_id=intervention.id,
        counselor_id=current_user.id,
        counselor_name=current_user.name,
        scheduled_at=payload.scheduled_at,
        status="Active",
        message_to_student=payload.message_to_student,
        message_to_faculty=payload.message_to_faculty,
        notes=payload.notes,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions_for_user(db: Session, current_user: User) -> list[CounselingSession]:
    query = db.query(CounselingSession)

    if current_user.role == UserRole.admin:
        return query.order_by(CounselingSession.scheduled_at.desc()).all()

    if current_user.role == UserRole.counselor:
        return query.filter(CounselingSession.counselor_id == current_user.id).order_by(CounselingSession.scheduled_at.desc()).all()

    if current_user.role == UserRole.faculty:
        if not current_user.assigned_class:
            return []
        return (
            query.join(Student, Student.id == CounselingSession.student_id)
            .filter(Student.class_name == current_user.assigned_class)
            .order_by(CounselingSession.scheduled_at.desc())
            .all()
        )

    if current_user.role == UserRole.student:
        student = _resolve_student_for_user(db, current_user)
        return query.filter(CounselingSession.student_id == student.id).order_by(CounselingSession.scheduled_at.desc()).all()

    return []


def complete_session(db: Session, session_id: int, payload: CounselingSessionComplete, current_user: User) -> CounselingSession:
    if current_user.role not in (UserRole.counselor, UserRole.admin):
        raise HTTPException(status_code=403, detail="Only counselor/admin can complete sessions")

    session = db.query(CounselingSession).filter(CounselingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = "Completed"
    session.completion_notes = payload.completion_notes

    intervention = None
    if session.intervention_id:
        intervention = db.query(Intervention).filter(Intervention.id == session.intervention_id).first()

    if intervention:
        intervention.status = InterventionStatus.completed
        intervention.outcome = payload.outcome or InterventionOutcome.stable
        db.add(TimelineEvent(
            intervention_id=intervention.id,
            student_id=intervention.student_id,
            event_type="Counseling Completed",
            description=f"Counseling completed by {current_user.name}.",
        ))

    db.commit()
    db.refresh(session)
    return session
