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
    Main prediction function — backwards compatible with existing API routes.
    Uses both models and blends them.
    """
    # ── Model 1: Early Risk ──
    father_occ = "Daily Wage Worker" if family_income < 20000 else ("Farmer" if family_income < 40000 else "Government Job")
    mother_occ = "Homemaker" if family_income < 30000 else "Teacher"
    parent_edu = "HighSchool" if family_income < 25000 else "Graduate"

    early_score = predict_early_risk(
        family_income=family_income,
        scholarship=scholarship,
        education_loan=education_loan,
        father_occupation=father_occ,
        mother_occupation=mother_occ,
        parent_education=parent_edu,
        home_location=home_location,
        hs_grade=hs_grade,
        admission_quota=admission_quota,
    )

    # ── Model 2: Dynamic Risk ──
    att_avg_4w = attendance + (att_slope * 2)  # estimate
    att_total_drop = max(0, 85 - attendance)
    has_ia = 1 if weeks_tracked >= 3 else 0
    ia_latest = marks * 0.4 if has_ia else 0.0  # rough: marks/100 * 40
    fee_outstanding = 1 if has_financial_issue else 0
    backlog_growing = 1 if (backlog_count > 0 and att_slope < 0) else 0

    dynamic_score = predict_dynamic_risk(
        att_current=attendance,
        att_avg_4w=float(np.clip(att_avg_4w, 20, 100)),
        att_total_drop=att_total_drop,
        att_slope=att_slope,
        ia_latest=ia_latest,
        ia_avg=ia_latest,
        has_ia_data=has_ia,
        backlog_current=backlog_count,
        backlog_growing=backlog_growing,
        fee_outstanding=fee_outstanding,
        weeks_tracked=weeks_tracked,
        family_income=family_income,
        hs_grade=hs_grade,
        home_location=home_location,
    )

    final_score = blend_scores(early_score, dynamic_score, weeks_tracked)

    # Determine risk level
    if final_score >= 70:
        level = "high"
    elif final_score >= 40:
        level = "medium"
    else:
        level = "low"

    # Derive factors
    factors = []
    if has_financial_issue:
        factors.append("financial")
    if attendance < 60:
        factors.append("attendance")
    if marks < 40:
        factors.append("academic")
    if has_family_issue:
        factors.append("family")
    if att_slope < -3:
        factors.append("declining_trend")

    # Recommendation
    if level == "high":
        if "financial" in factors and "attendance" in factors:
            rec = "Immediate counseling + financial support required. Schedule within 24 hours."
        elif "attendance" in factors or "declining_trend" in factors:
            rec = "Critical attendance drop. Faculty must reach out and assign academic mentorship."
        elif "financial" in factors:
            rec = "Financial stress is primary driver. Connect with financial aid office immediately."
        else:
            rec = "Multiple risk factors detected. Assign a counselor and create intervention plan."
    elif level == "medium":
        rec = "Monitor closely. Consider preventive counseling and attendance follow-up."
    else:
        rec = "Student is currently low risk. Continue regular monitoring."

    return {
        "risk_score": final_score,
        "baseline_risk_score": early_score,
        "dynamic_risk_score": dynamic_score,
        "risk_level": level,
        "is_high_risk": level == "high",
        "risk_factors": factors,
        "recommendation": rec,
        "confidence": round(final_score / 100, 3),
        "weeks_tracked": weeks_tracked,
    }
