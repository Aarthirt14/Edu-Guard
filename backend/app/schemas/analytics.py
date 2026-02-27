# ============================================================
# app/schemas/analytics.py — Analytics response schemas
# ============================================================
from pydantic import BaseModel
from typing import List, Dict


class DashboardStats(BaseModel):
    total_high_risk: int
    new_high_risk_this_week: int
    active_interventions: int
    improved_after_intervention: int


class RiskTrendPoint(BaseModel):
    month: str
    count: int


class FactorDistribution(BaseModel):
    financial: int
    attendance: int
    academic: int
    family: int


class InterventionSuccessBreakdown(BaseModel):
    improved: int
    stable: int
    no_change: int
    declined: int


class AnalyticsResponse(BaseModel):
    risk_trend: List[RiskTrendPoint]
    factor_distribution: FactorDistribution
    intervention_success: InterventionSuccessBreakdown


class AIChatRequest(BaseModel):
    message: str

    model_config = {"json_schema_extra": {"example": {"message": "Which students need immediate attention?"}}}


class AIChatResponse(BaseModel):
    reply: str
