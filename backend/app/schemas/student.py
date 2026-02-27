# ============================================================
# app/schemas/student.py — Student request/response schemas
# ============================================================
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class StudentBase(BaseModel):
    name: str
    email: Optional[str] = None
    class_name: str
    semester: str
    attendance: float = Field(ge=0, le=100)
    marks: float = Field(ge=0, le=100)
    has_financial_issue: bool = False
    has_family_issue: bool = False


class StudentCreate(StudentBase):
    id: str  # "STU-xxxx"


class StudentUpdate(BaseModel):
    attendance: Optional[float] = Field(None, ge=0, le=100)
    marks: Optional[float] = Field(None, ge=0, le=100)
    has_financial_issue: Optional[bool] = None
    has_family_issue: Optional[bool] = None
    counselor_id: Optional[str] = None


class StudentOut(StudentBase):
    id: str
    risk_score: float
    risk_trend: str
    risk_factors: List[str]
    counselor_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---- Prediction ----

class PredictRequest(BaseModel):
    attendance: float = Field(..., ge=0, le=100, description="Attendance percentage")
    marks: float = Field(..., ge=0, le=100, description="Average marks out of 100")
    has_financial_issue: bool = False
    has_family_issue: bool = False
    semester: Optional[int] = Field(None, ge=1, le=8)

    model_config = {"json_schema_extra": {
        "example": {
            "attendance": 48.0,
            "marks": 32.0,
            "has_financial_issue": True,
            "has_family_issue": False,
            "semester": 4
        }
    }}


class PredictResponse(BaseModel):
    risk_score: float = Field(..., description="Score 0-100, higher = more at risk")
    risk_level: str = Field(..., description="high | medium | low")
    is_high_risk: bool
    risk_factors: List[str]
    recommendation: str
    confidence: float
