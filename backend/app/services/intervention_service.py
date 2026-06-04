# ============================================================
# app/services/intervention_service.py — Intervention Logic
# ============================================================
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from typing import List
from app.models.intervention import Intervention, InterventionStatus, InterventionOutcome, TimelineEvent, InterventionType
from app.models.student import Student
from app.models.user import User
from app.schemas.intervention import InterventionCreate, InterventionUpdate, InterventionStats
import logging

logger = logging.getLogger(__name__)


def create_intervention(db: Session, data: InterventionCreate, current_user: User) -> Intervention:
    student = db.query(Student).filter(Student.id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    iv = Intervention(
        student_id=data.student_id,
        type=data.type,
        assigned_by=current_user.name,
        assigned_by_id=current_user.id,
        notes=data.notes,
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

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(iv, field, value)

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
