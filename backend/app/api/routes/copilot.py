from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.copilot import CopilotRunOut, CopilotRunDetail, CopilotRunRequest
from app.services.auth_service import require_role
from app.services.copilot_service import run_weekly_copilot, list_copilot_runs, get_copilot_run_detail

router = APIRouter(prefix="/copilot", tags=["Early Warning Copilot"])


@router.post("/runs", response_model=CopilotRunOut, summary="Run weekly Early Warning Copilot")
async def run_copilot(
    payload: CopilotRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    return await run_weekly_copilot(db, run_by=current_user, run_type=payload.run_type)


@router.get("/runs", response_model=List[CopilotRunOut], summary="List recent copilot runs")
def get_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.counselor)),
):
    return list_copilot_runs(db, limit=limit)


@router.get("/runs/{run_id}", response_model=CopilotRunDetail, summary="Get copilot run detail with action tickets")
def get_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.counselor)),
):
    return get_copilot_run_detail(db, run_id)
