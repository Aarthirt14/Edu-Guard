# ============================================================
# app/schemas/intervention.py — Intervention schemas
# ============================================================
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.intervention import InterventionType, InterventionStatus, InterventionOutcome


class InterventionCreate(BaseModel):
    student_id: str
    type: InterventionType
    notes: Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {
            "student_id": "STU-1024",
            "type": "Counseling",
            "notes": "Student showed signs of stress. Scheduled weekly sessions."
        }
    }}


class InterventionUpdate(BaseModel):
    status: Optional[InterventionStatus] = None
    outcome: Optional[InterventionOutcome] = None
    notes: Optional[str] = None


class InterventionOut(BaseModel):
    id: int
    student_id: str
    student_name: Optional[str] = None
    class_name: Optional[str] = None
    type: InterventionType
    assigned_by: str
    status: InterventionStatus
    outcome: InterventionOutcome
    notes: Optional[str] = None
    ai_support_note: Optional[str] = None
    ai_support_source: Optional[str] = None
    date_assigned: datetime

    model_config = {"from_attributes": True}


class TimelineEventOut(BaseModel):
    id: int
    event_type: str
    description: str
    recorded_at: datetime

    model_config = {"from_attributes": True}


class InterventionStats(BaseModel):
    total: int
    pending: int
    active: int
    completed: int
    improved: int
    success_rate: float
