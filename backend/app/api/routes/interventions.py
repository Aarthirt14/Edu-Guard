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

from app.db.database import get_db
from app.schemas.intervention import (InterventionCreate, InterventionUpdate,
                                       InterventionOut, TimelineEventOut, InterventionStats)
from app.services.intervention_service import (create_intervention, list_interventions,
                                                update_intervention, get_timeline,
                                                get_intervention_stats)
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
    _: User = Depends(require_role(UserRole.admin, UserRole.counselor)),
):
    ivs = list_interventions(db, student_id)
    result = []
    for iv in ivs:
        out = InterventionOut.model_validate(iv)
        out.student_name = iv.student.name if iv.student else None
        result.append(out)
    return result


@router.post("/", response_model=InterventionOut, status_code=201, summary="Assign a new intervention")
def create(
    data: InterventionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.counselor, UserRole.faculty)),
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
    return get_timeline(db, student_id)
