from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from app.models.intervention import InterventionOutcome


class CounselingSessionCreate(BaseModel):
    student_id: str
    scheduled_at: datetime
    message_to_student: Optional[str] = None
    message_to_faculty: Optional[str] = None
    notes: Optional[str] = None


class CounselingSessionComplete(BaseModel):
    completion_notes: Optional[str] = None
    outcome: Optional[InterventionOutcome] = InterventionOutcome.stable


class CounselingSessionOut(BaseModel):
    id: int
    student_id: str
    student_name: Optional[str] = None
    class_name: Optional[str] = None
    intervention_id: Optional[int] = None
    counselor_id: Optional[str] = None
    counselor_name: str
    scheduled_at: datetime
    status: str
    message_to_student: Optional[str] = None
    message_to_faculty: Optional[str] = None
    notes: Optional[str] = None
    completion_notes: Optional[str] = None

    model_config = {"from_attributes": True}


class CounselingStats(BaseModel):
    active: int
    completed: int
