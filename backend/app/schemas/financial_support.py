from typing import Optional, List

from pydantic import BaseModel


class StudentFinancialInput(BaseModel):
    fee_outstanding_amount: Optional[float] = None
    scholarship_eligibility: Optional[str] = None
    social_category: Optional[str] = None
    parent_occupation: Optional[str] = None
    family_income_band: Optional[str] = None
    scholarship_applied: Optional[str] = None
    preferred_support_type: Optional[str] = None
    student_notes: Optional[str] = None


class AdminFinancialPlanInput(BaseModel):
    admin_plan_type: Optional[str] = None
    admin_plan: Optional[str] = None
    admin_notes: Optional[str] = None
    status: Optional[str] = None


class FinancialSupportCaseOut(BaseModel):
    id: int
    intervention_id: int
    student_id: str
    student_name: Optional[str] = None
    status: str

    fee_outstanding_amount: Optional[float] = None
    scholarship_eligibility: Optional[str] = None
    social_category: Optional[str] = None
    parent_occupation: Optional[str] = None
    family_income_band: Optional[str] = None
    scholarship_applied: Optional[str] = None
    preferred_support_type: Optional[str] = None
    student_notes: Optional[str] = None

    ai_summary: Optional[str] = None
    ai_recommendations: Optional[List[str]] = None

    admin_plan_type: Optional[str] = None
    admin_plan: Optional[str] = None
    admin_notes: Optional[str] = None

    model_config = {"from_attributes": True}
