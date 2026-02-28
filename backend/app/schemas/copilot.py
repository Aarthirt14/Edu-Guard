from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel


class CopilotRunRequest(BaseModel):
    run_type: str = "weekly"


class CopilotActionTicketOut(BaseModel):
    id: int
    run_id: int
    student_id: str
    student_name: Optional[str] = None
    class_name: Optional[str] = None
    risk_score: float
    risk_trend: Optional[str] = None
    reason_summary: str
    recommended_intervention: str
    priority: str
    n8n_status: str
    n8n_reference: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CopilotRunOut(BaseModel):
    id: int
    run_type: str
    status: str
    total_students_scanned: int
    high_risk_identified: int
    actions_created: int
    summary: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CopilotRunDetail(BaseModel):
    run: CopilotRunOut
    tickets: List[CopilotActionTicketOut]
