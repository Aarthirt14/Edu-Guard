# ============================================================
# app/schemas/intervention.py — Intervention schemas
# ============================================================
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.intervention import InterventionType, InterventionStatus, InterventionOutcome


class InterventionCreate(BaseModel):
    owner_id: Optional[str] = None
    due_at: Optional[datetime] = None
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
    owner_id: Optional[str] = None
    due_at: Optional[datetime] = None
    closure_reason: Optional[str] = Field(None, max_length=2000)
    follow_up_observation: Optional[str] = Field(None, max_length=4000)
    follow_up_attendance: Optional[float] = Field(None, ge=0, le=100)
    follow_up_marks: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[InterventionStatus] = None
    outcome: Optional[InterventionOutcome] = None
    notes: Optional[str] = None


class InterventionOut(BaseModel):
    owner_id: Optional[str] = None
    due_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    closure_reason: Optional[str] = None
    follow_up_observation: Optional[str] = None
    baseline_attendance: Optional[float] = None
    follow_up_attendance: Optional[float] = None
    baseline_marks: Optional[float] = None
    follow_up_marks: Optional[float] = None
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
