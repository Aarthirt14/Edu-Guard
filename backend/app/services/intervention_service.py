# ============================================================
# app/services/intervention_service.py — Intervention Logic
# ============================================================
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from typing import List
from app.models.intervention import Intervention, InterventionStatus, InterventionOutcome, TimelineEvent, InterventionType
from app.models.student import Student
from app.models.user import User, UserRole
from datetime import datetime, timezone, timedelta
from app.schemas.intervention import InterventionCreate, InterventionUpdate, InterventionStats
import logging

logger = logging.getLogger(__name__)


def create_intervention(db: Session, data: InterventionCreate, current_user: User) -> Intervention:
    student = db.query(Student).filter(Student.id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    validate_owner(db, data.owner_id or current_user.id)
    iv = Intervention(
        student_id=data.student_id,
        type=data.type,
        assigned_by=current_user.name,
        assigned_by_id=current_user.id,
        notes=data.notes,
        owner_id=data.owner_id or current_user.id,
        due_at=data.due_at or datetime.now(timezone.utc) + timedelta(days=7),
        initial_risk_score=student.risk_score,
        baseline_attendance=student.attendance,
        baseline_marks=student.marks,
    )
    db.add(iv)
    db.flush()

    # Auto-create first timeline event
    db.add(TimelineEvent(
        intervention_id=iv.id,
        student_id=data.student_id,
        event_type="Intervention Created",
        description=f"{data.type.value} assigned by {current_user.name}.",
    ))

    if data.type.value == "Financial Support":
        from app.services.financial_support_service import ensure_financial_case_for_intervention
        ensure_financial_case_for_intervention(db, iv)

    # Update student intervention status
    student_ivs = db.query(Intervention).filter(
        Intervention.student_id == data.student_id,
        Intervention.status == InterventionStatus.active
    ).count()
    db.commit()
    db.refresh(iv)
    return iv


def list_interventions(
    db: Session,
    student_id: str = None,
    intervention_type: str | None = None,
    class_name: str | None = None,
) -> List[Intervention]:
    query = db.query(Intervention).options(joinedload(Intervention.student))

    if class_name:
        query = query.join(Student, Intervention.student_id == Student.id).filter(Student.class_name == class_name)

    if student_id:
        query = query.filter(Intervention.student_id == student_id)

    if intervention_type:
        try:
            query = query.filter(Intervention.type == InterventionType(intervention_type))
        except Exception:
            return []

    return query.order_by(Intervention.date_assigned.desc()).all()


def update_intervention(db: Session, iv_id: int, data: InterventionUpdate, current_user: User) -> Intervention:
    iv = db.query(Intervention).filter(Intervention.id == iv_id).first()
    if not iv:
        raise HTTPException(status_code=404, detail="Intervention not found")

    if data.owner_id:
        validate_owner(db, data.owner_id)
    if "status" in data.model_fields_set and data.status is None:
        raise HTTPException(422, "Status cannot be null")
    if "outcome" in data.model_fields_set and data.outcome is None:
        raise HTTPException(422, "Outcome cannot be null")
    if data.status == InterventionStatus.completed:
        if not (data.closure_reason or iv.closure_reason or "").strip():
            raise HTTPException(422, "A closure reason is required")
        if not (data.follow_up_observation or iv.follow_up_observation or "").strip():
            raise HTTPException(422, "A follow-up observation is required")
        iv.final_risk_score = iv.student.risk_score
    if data.status == InterventionStatus.active and iv.accepted_at is None:
        iv.accepted_at = datetime.now(timezone.utc)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(iv, field, value)

    if data.follow_up_observation:
        db.add(TimelineEvent(intervention_id=iv.id, student_id=iv.student_id,
            event_type="Follow-up recorded", description=f"{current_user.name}: {data.follow_up_observation}"))
    # Log status change to timeline
    if data.status:
        db.add(TimelineEvent(
            intervention_id=iv.id,
            student_id=iv.student_id,
            event_type="Status Update",
            description=f"Status changed to {data.status.value} by {current_user.name}.",
        ))

    db.commit()
    db.refresh(iv)
    return iv


def get_timeline(db: Session, student_id: str) -> List[TimelineEvent]:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return (db.query(TimelineEvent)
              .filter(TimelineEvent.student_id == student_id)
              .order_by(TimelineEvent.recorded_at.asc())
              .all())


def get_intervention_stats(db: Session) -> InterventionStats:
    total = db.query(Intervention).count()
    pending = db.query(Intervention).filter(Intervention.status == InterventionStatus.pending).count()
    active = db.query(Intervention).filter(Intervention.status == InterventionStatus.active).count()
    completed = db.query(Intervention).filter(Intervention.status == InterventionStatus.completed).count()
    improved = db.query(Intervention).filter(
        Intervention.outcome.in_([InterventionOutcome.improved, InterventionOutcome.improving])
    ).count()
    success_rate = round((improved / total * 100) if total > 0 else 0, 1)
    return InterventionStats(total=total, pending=pending, active=active,
                             completed=completed, improved=improved, success_rate=success_rate)


def validate_owner(db, owner_id):
    owner = db.get(User, owner_id)
    if not owner or not owner.is_active or owner.role not in (UserRole.admin, UserRole.counselor, UserRole.faculty):
        raise HTTPException(422, "Owner must be an active staff account")
