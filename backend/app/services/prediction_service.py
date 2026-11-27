"""One authoritative student prediction, shared by uploads, API and Copilot.

Scores are uncalibrated synthetic-model outputs, not verified dropout probabilities.
Feature replacement explanations are sensitivities, not causal/additive attributions.
"""
from datetime import datetime, timezone
import hashlib
import json
import numpy as np
import pandas as pd
from app.models.student import Student, WeeklyRecord, RiskHistory
from app.ml.model import blend_scores
from app.ml.train_models import load_early_model, load_dynamic_model

VERSION = "eduguard-v3"
EARLY_FIELDS = {
    "Family_Income": "family_income", "Scholarship": "scholarship",
    "Education_Loan": "education_loan", "Father_Occupation": "father_occupation",
    "Mother_Occupation": "mother_occupation", "Parent_Education": "parent_education",
    "Home_Location": "home_location", "HighSchool_Grade": "hs_grade",
}


def _score(model, features):
    return float(model.predict_proba(pd.DataFrame([features]))[0, 1] * 100)


def _explain(model, features, score, weight, component):
    reference = getattr(model, "eduguard_reference", {})
    rows = []
    for name, value in features.items():
        if name not in reference:
            continue
        changed = dict(features, **{name: reference[name]})
        delta = (score - _score(model, changed)) * weight
        rows.append({"feature": name, "value": value, "reference": reference[name],
                     "score_change_points": round(delta, 2), "component": component})
    return rows


def predict_student(db, student):
    records = db.query(WeeklyRecord).filter(WeeklyRecord.student_id == student.id).order_by(WeeklyRecord.week_number).all()
    missing = [attr for attr in EARLY_FIELDS.values() if getattr(student, attr) in (None, "")]
    early_features = {key: getattr(student, attr) for key, attr in EARLY_FIELDS.items()}
    early_model = load_early_model() if not missing else None
    early = _score(early_model, early_features) if early_model is not None else None
    dynamic = None
    features = {}
    dynamic_model = None
    if records:
        attendance = [r.attendance_pct for r in records]
        weeks = [r.week_number for r in records]
        marks = [r.ia_marks for r in records if r.ia_marks is not None]
        features = {
            "att_current": attendance[-1], "att_avg_4w": float(np.mean(attendance[-4:])),
            "att_total_drop": attendance[0] - attendance[-1],
            "att_slope": float(np.polyfit(weeks, attendance, 1)[0]) if len(records) > 1 else 0.,
            "ia_latest": marks[-1] if marks else 0., "ia_avg": float(np.mean(marks)) if marks else 0.,
            "has_ia_data": int(bool(marks)), "backlog_current": records[-1].backlog_count or 0,
            "backlog_growing": int(len(records) > 1 and (records[-1].backlog_count or 0) > (records[-2].backlog_count or 0)),
            "fee_outstanding": int(records[-1].fee_outstanding), "weeks_tracked": len(records),
        }
        # At least two real observations are needed for a trend-based model.
        if len(records) >= 2:
            dynamic_model = load_dynamic_model()
            dynamic = _score(dynamic_model, features)
    weeks_tracked = len(records)
    if early is not None and dynamic is not None:
        total = blend_scores(early, dynamic, weeks_tracked)
        early_weight = .6 if weeks_tracked <= 2 else (.4 if weeks_tracked <= 7 else .2)
        mode = "combined"
    elif early is not None:
        total, early_weight, mode = early, 1., "admission_only"
    elif dynamic is not None:
        total, early_weight, mode = dynamic, 0., "weekly_only"
    else:
        total, early_weight, mode = None, 0., "insufficient_data"
    explanations = []
    if early is not None:
        explanations += _explain(early_model, early_features, early, early_weight, "admission")
    if dynamic is not None:
        explanations += _explain(dynamic_model, features, dynamic, 1 - early_weight, "weekly")
    explanations.sort(key=lambda x: abs(x["score_change_points"]), reverse=True)
    inputs = {"admission": early_features, "weekly": features}
    fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:16]
    result = {
        "risk_score": round(total, 1) if total is not None else None,
        "risk_level": "unknown" if total is None else ("high" if total >= 70 else "medium" if total >= 40 else "low"),
        "baseline_risk_score": round(early, 1) if early is not None else None,
        "dynamic_risk_score": round(dynamic, 1) if dynamic is not None else None,
        "mode": mode, "weeks_tracked": weeks_tracked, "input_fingerprint": fingerprint,
        "model_version": VERSION, "validation_status": "synthetic_demo_not_real_world_validated",
        "score_meaning": "Uncalibrated model score; not a confirmed dropout probability",
        "missing_admission_fields": missing,
        "data_completeness": round((len(EARLY_FIELDS) - len(missing)) / len(EARLY_FIELDS), 2),
        "data_completeness_scope": "admission fields only; not prediction confidence",
        "weekly_features": features,
        "explanation_method": "Replace one feature with its training reference; changes are not additive or causal",
        "explanations": explanations[:6],
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }
    return result


def refresh_prediction(db, student):
    result = predict_student(db, student)
    previous = student.risk_score
    student.risk_score = result["risk_score"]
    student.baseline_risk_score = result["baseline_risk_score"]
    student.dynamic_risk_score = result["dynamic_risk_score"]
    student.weeks_tracked = result["weeks_tracked"]
    student.risk_trend = "stable" if previous is None or student.risk_score is None or previous == student.risk_score else "up" if student.risk_score > previous else "down"
    old = student.prediction or {}
    # Identical uploads must not generate duplicate risk-history entries.
    if old.get("input_fingerprint") != result["input_fingerprint"] or old.get("model_version") != VERSION:
        student.prediction = result
        if student.risk_score is not None:
            db.add(RiskHistory(student_id=student.id, risk_score=student.risk_score, prediction=result))
    return student.prediction
