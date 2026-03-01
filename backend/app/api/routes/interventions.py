# ============================================================
# app/api/routes/interventions.py
# GET  /api/interventions/          → list all
# POST /api/interventions/          → create
# PUT  /api/interventions/{id}      → update status/outcome
# GET  /api/interventions/stats     → counts for stat cards
# GET  /api/interventions/{sid}/timeline → student timeline
# ============================================================
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
import re

from app.db.database import get_db
from app.schemas.intervention import (InterventionCreate, InterventionUpdate,
                                       InterventionOut, TimelineEventOut, InterventionStats)
from app.services.intervention_service import (create_intervention, list_interventions,
                                                update_intervention, get_timeline,
                                                get_intervention_stats)
from app.services.academic_support_ai_service import generate_academic_support_note
from app.services.auth_service import get_current_user, require_role
from app.models.user import User, UserRole

router = APIRouter(prefix="/interventions", tags=["Interventions"])


@router.get("/stats", response_model=InterventionStats, summary="Stat card numbers for Intervention page")
def stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.counselor)),
):
    return get_intervention_stats(db)


@router.get("/", response_model=List[InterventionOut], summary="List all interventions")
def list_all(
    student_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.counselor, UserRole.faculty)),
):
    intervention_type = None
    class_name = None
    if current_user.role == UserRole.faculty:
        if not current_user.assigned_class:
            return []
        intervention_type = "Academic Support"
        class_name = current_user.assigned_class

    ivs = list_interventions(
        db,
        student_id=student_id,
        intervention_type=intervention_type,
        class_name=class_name,
    )
    result = []
    for iv in ivs:
        out = InterventionOut.model_validate(iv)
        out.student_name = iv.student.name if iv.student else None
        out.class_name = iv.student.class_name if iv.student else None

        if (
            current_user.role == UserRole.faculty
            and out.type.value == "Academic Support"
            and (not out.notes or not str(out.notes).strip())
            and iv.student is not None
        ):
            ai_note, ai_source = generate_academic_support_note(db, iv.student, iv)
            out.ai_support_note = ai_note
            out.ai_support_source = ai_source

        result.append(out)
    return result


@router.post("/", response_model=InterventionOut, status_code=201, summary="Assign a new intervention")
def create(
    data: InterventionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.counselor)),
):
    """
    Called from the "Assign Intervention" modal.
    Automatically sets `assigned_by` from the JWT token.
    """
    return create_intervention(db, data, current_user)


@router.put("/{iv_id}", response_model=InterventionOut, summary="Update intervention status or outcome")
def update(
    iv_id: int,
    data: InterventionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.counselor)),
):
    return update_intervention(db, iv_id, data, current_user)


@router.get("/{student_id}/timeline", response_model=List[TimelineEventOut],
            summary="Get intervention timeline for a student")
def timeline(
    student_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Used by the Timeline Modal in the frontend."""
    events = get_timeline(db, student_id)
    cleaned: List[TimelineEventOut] = []
    for evt in events:
        out = TimelineEventOut.model_validate(evt)
        out.description = re.sub(r"\s*\[RAG:[\s\S]*?\]\s*$", "", str(out.description or ""), flags=re.IGNORECASE).strip()
        cleaned.append(out)
    return cleaned
