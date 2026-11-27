"""
app/ml/model.py
Unified predictor combining Model 1 (Early Risk) + Model 2 (Dynamic Risk)
with the blended scoring formula from the spec:

  Weeks 1–2:  60% early + 40% dynamic
  Weeks 3–7:  40% early + 60% dynamic
  Weeks 8+:   20% early + 80% dynamic
"""
import numpy as np
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Categorical values for ordinal encoding (must match training data)
SCHOLARSHIPS = ["No", "Yes"]
LOANS = ["No", "Yes"]
FATHER_OCCUPATIONS = ["Daily Wage Worker", "Farmer", "Small Business", "Government Job",
                       "Engineer", "Doctor", "Teacher", "Factory Worker", "Driver", "Shopkeeper"]
MOTHER_OCCUPATIONS = ["Homemaker", "Daily Wage Worker", "Teacher", "Government Job",
                      "Shopkeeper", "Nurse", "Farmer", "Factory Worker"]
PARENT_EDUCATIONS = ["No Formal Education", "Primary School", "HighSchool", "Diploma",
                     "Graduate", "Postgraduate"]
HOME_LOCATIONS = ["Rural", "Semi-Urban", "Urban"]
ADMISSION_QUOTAS = ["Management", "Merit", "NRI", "SC/ST", "OBC", "Sports"]


def load_model():
    """Called at startup to warm up both models."""
    from app.ml.train_models import load_both_models
    load_both_models()
    logger.info("✅ Both ML models loaded")


def predict_early_risk(
    family_income: float,
    scholarship: str,        # "Yes"/"No"
    education_loan: str,     # "Yes"/"No"
    father_occupation: str,
    mother_occupation: str,
    parent_education: str,
    home_location: str,
    hs_grade: float,
    admission_quota: str,
) -> float:
    """
    Model 1 — Early Risk Score (0–100).
    Runs once at admission and never changes.
    """
    from app.ml.train_models import load_early_model
    pipeline = load_early_model()

    X = pd.DataFrame([{
        "Family_Income": family_income,
        "Scholarship": scholarship,
        "Education_Loan": education_loan,
        "Father_Occupation": father_occupation,
        "Mother_Occupation": mother_occupation,
        "Parent_Education": parent_education,
        "Home_Location": home_location,
        "HighSchool_Grade": hs_grade,
        "Admission_Quota": admission_quota,
    }])

    proba = pipeline.predict_proba(X)[0][1]
    return round(float(proba * 100), 1)


def predict_dynamic_risk(
    att_current: float,
    att_avg_4w: float,
    att_total_drop: float,
    att_slope: float,
    ia_latest: float,
    ia_avg: float,
    has_ia_data: int,
    backlog_current: int,
    backlog_growing: int,
    fee_outstanding: int,
    weeks_tracked: int,
    family_income: float,
    hs_grade: float,
    home_location: str,
) -> float:
    """
    Model 2 — Dynamic Risk Score (0–100).
    Re-computed every week after faculty CSV upload.
    """
    from app.ml.train_models import load_dynamic_model
    pipeline = load_dynamic_model()

    X = pd.DataFrame([{
        "att_current": att_current,
        "att_avg_4w": att_avg_4w,
        "att_total_drop": att_total_drop,
        "att_slope": att_slope,
        "ia_latest": ia_latest,
        "ia_avg": ia_avg,
        "has_ia_data": has_ia_data,
        "backlog_current": backlog_current,
        "backlog_growing": backlog_growing,
        "fee_outstanding": fee_outstanding,
        "weeks_tracked": weeks_tracked,
        "Family_Income": family_income,
        "HighSchool_Grade": hs_grade,
        "Home_Location": home_location,
    }])

    proba = pipeline.predict_proba(X)[0][1]
    return round(float(proba * 100), 1)


def blend_scores(early_score: float, dynamic_score: float, weeks_tracked: int) -> float:
    """
    Blends early (admission) + dynamic (weekly) scores per spec:
      Weeks 1–2:  60% early + 40% dynamic
      Weeks 3–7:  40% early + 60% dynamic
      Weeks 8+:   20% early + 80% dynamic
    """
    if weeks_tracked <= 2:
        w_early, w_dynamic = 0.60, 0.40
    elif weeks_tracked <= 7:
        w_early, w_dynamic = 0.40, 0.60
    else:
        w_early, w_dynamic = 0.20, 0.80

    blended = w_early * early_score + w_dynamic * dynamic_score
    return round(min(100.0, max(0.0, blended)), 1)


def predict_risk(
    attendance: float,
    marks: float,
    has_financial_issue: bool,
    has_family_issue: bool,
    semester: int = 4,
    # Extended params for proper dual-model prediction
    family_income: float = 20000,
    hs_grade: float = 65,
    home_location: str = "Semi-Urban",
    scholarship: str = "No",
    education_loan: str = "No",
    admission_quota: str = "Merit",
    weeks_tracked: int = 4,
    att_slope: float = -2.0,
    backlog_count: int = 0,
) -> dict:
    """
    Legacy hypothetical scenario preview, not used for student scoring.
    Uses both models and blends them.
    """
    # A single snapshot cannot supply observed weekly trends or an admission profile.
    factors = []
    if attendance < 60:
        factors.append("attendance")
    if marks < 40:
        factors.append("academic")
    if has_financial_issue:
        factors.append("financial")
    if has_family_issue:
        factors.append("family")
    return {"risk_score": None, "risk_level": "unknown", "is_high_risk": False,
            "risk_factors": factors, "recommendation": "Upload admission data or at least two weekly records for a model score.",
            "data_status": "insufficient_data", "validation_status": "not_validated_on_real_outcomes"}
