"""
generate_datasets.py — Generates both training datasets:
  1. students_static.csv   — for Model 1 (Early Risk / Admission) - RandomForest
  2. engineered_training_data.csv — for Model 2 (Dynamic Risk / Weekly) - GradientBoosting

Run: python -m app.ml.generate_datasets
"""

import numpy as np
import pandas as pd
import os
from pathlib import Path

DATA_DIR = Path(os.path.dirname(__file__)) / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

np.random.seed(42)

FATHER_OCCUPATIONS = ["Daily Wage Worker", "Farmer", "Small Business", "Government Job",
                       "Engineer", "Doctor", "Teacher", "Factory Worker", "Driver", "Shopkeeper"]
MOTHER_OCCUPATIONS = ["Homemaker", "Daily Wage Worker", "Teacher", "Government Job",
                      "Shopkeeper", "Nurse", "Farmer", "Factory Worker"]
PARENT_EDUCATIONS = ["No Formal Education", "Primary School", "HighSchool", "Diploma",
                     "Graduate", "Postgraduate"]
HOME_LOCATIONS = ["Rural", "Semi-Urban", "Urban"]
ADMISSION_QUOTAS = ["Management", "Merit", "NRI", "SC/ST", "OBC", "Sports"]
BATCHES = [2021, 2022, 2023, 2024]


# ─────────────────────────────────────────────────────────────
# MODEL 1 — students_static.csv  (10,000 rows)
# ─────────────────────────────────────────────────────────────

def generate_static_data(n: int = 10000) -> pd.DataFrame:
    """
    Generates admission-time static features for Model 1.
    Label: Dropout (0/1)

    Risk logic aligned with domain spec:
      - Low income + rural + low HS grade + no scholarship → high baseline risk
    """
    rng = np.random.default_rng(42)

    family_income = rng.choice(
        [3000, 5000, 8000, 12000, 18000, 25000, 35000, 45000, 60000, 75000, 100000],
        size=n,
        p=[0.04, 0.07, 0.10, 0.14, 0.13, 0.12, 0.12, 0.10, 0.08, 0.06, 0.04]
    )

    scholarship = rng.choice([0, 1], size=n, p=[0.55, 0.45])
    education_loan = rng.choice([0, 1], size=n, p=[0.60, 0.40])

    father_occ_idx = rng.choice(len(FATHER_OCCUPATIONS), size=n)
    mother_occ_idx = rng.choice(len(MOTHER_OCCUPATIONS), size=n)
    parent_edu_idx = rng.choice(len(PARENT_EDUCATIONS), size=n,
                                 p=[0.06, 0.10, 0.22, 0.18, 0.28, 0.16])
    home_loc_idx = rng.choice(len(HOME_LOCATIONS), size=n, p=[0.38, 0.30, 0.32])
    hs_grade = rng.uniform(40, 99, size=n)
    admission_quota_idx = rng.choice(len(ADMISSION_QUOTAS), size=n,
                                      p=[0.18, 0.40, 0.05, 0.18, 0.12, 0.07])

    # Compute dropout probability using domain rules
    risk_score = np.zeros(n)

    # Income factor (lower income → higher risk)
    income_norm = np.clip(family_income / 100000, 0, 1)
    risk_score += (1 - income_norm) * 30

    # Scholarship reduces risk
    risk_score -= scholarship * 12

    # Education loan increases pressure slightly
    risk_score += education_loan * 5

    # Parent education (lower → higher risk)
    risk_score += (1 - parent_edu_idx / (len(PARENT_EDUCATIONS) - 1)) * 18

    # Home location (rural → higher risk)
    loc_risk = [12, 5, 0]
    risk_score += np.array([loc_risk[i] for i in home_loc_idx])

    # High school grade (lower → higher risk)
    risk_score += (100 - hs_grade) * 0.25

    # Father occupation risk
    father_risk = [25, 22, 10, 5, 2, 2, 4, 18, 15, 8]
    risk_score += np.array([father_risk[i] for i in father_occ_idx])

    # Admission quota
    quota_risk = [8, 0, 3, 12, 8, 5]
    risk_score += np.array([quota_risk[i] for i in admission_quota_idx])

    # Add noise
    risk_score += rng.normal(0, 6, size=n)
    risk_score = np.clip(risk_score, 0, 100)

    # Dropout label (threshold = 55 for ~35% dropout rate, realistic)
    dropout = (risk_score >= 55).astype(int)

    df = pd.DataFrame({
        "Family_Income": family_income.astype(int),
        "Scholarship": ["Yes" if s else "No" for s in scholarship],
        "Education_Loan": ["Yes" if e else "No" for e in education_loan],
        "Father_Occupation": [FATHER_OCCUPATIONS[i] for i in father_occ_idx],
        "Mother_Occupation": [MOTHER_OCCUPATIONS[i] for i in mother_occ_idx],
        "Parent_Education": [PARENT_EDUCATIONS[i] for i in parent_edu_idx],
        "Home_Location": [HOME_LOCATIONS[i] for i in home_loc_idx],
        "HighSchool_Grade": np.round(hs_grade, 1),
        "Admission_Quota": [ADMISSION_QUOTAS[i] for i in admission_quota_idx],
        "Dropout": dropout,
    })

    # Assign batch years (2021-2024, training batches only)
    df["Batch"] = rng.choice(BATCHES, size=n)

    print(f"✅ students_static.csv: {len(df)} rows | Dropout rate: {dropout.mean():.1%}")
    return df


# ─────────────────────────────────────────────────────────────
# MODEL 2 — engineered_training_data.csv  (10,000 rows)
# ─────────────────────────────────────────────────────────────

def _simulate_weekly_trajectory(n_weeks: int, rng: np.random.Generator,
                                 base_attendance: float, declining: bool):
    """Simulate weekly attendance values for one student."""
    weeks = np.arange(1, n_weeks + 1)
    if declining:
        slope = rng.uniform(-4, -1)
        noise = rng.normal(0, 3, n_weeks)
    else:
        slope = rng.uniform(0.5, 3)
        noise = rng.normal(0, 2, n_weeks)
    values = base_attendance + slope * (weeks - 1) + noise
    return np.clip(values, 20, 100)


def generate_engineered_data(n: int = 10000) -> pd.DataFrame:
    """
    Generates engineered weekly features for Model 2.
    Features include slope, averages, trends, + static background features.
    Label: Dropout (0/1)
    """
    rng = np.random.default_rng(123)
    records = []

    for _ in range(n):
        # Background (from static join)
        family_income = int(rng.choice(
            [5000, 10000, 18000, 30000, 50000, 75000],
            p=[0.15, 0.20, 0.20, 0.20, 0.15, 0.10]
        ))
        hs_grade = float(rng.uniform(40, 99))
        home_loc = rng.choice(HOME_LOCATIONS, p=[0.38, 0.30, 0.32])

        # Weeks tracked (1–16)
        weeks_tracked = int(rng.integers(2, 17))

        # Decide if student is declining or recovering
        declining = rng.random() < 0.45
        base_att = float(rng.uniform(35, 95))

        att_series = _simulate_weekly_trajectory(weeks_tracked, rng, base_att, declining)

        att_current = float(att_series[-1])
        last4 = att_series[-min(4, weeks_tracked):]
        att_avg_4w = float(np.mean(last4))
        att_total_drop = float(att_series[0] - att_current)
        att_slope = float(np.polyfit(np.arange(weeks_tracked), att_series, 1)[0])

        # IA marks (may or may not exist depending on week)
        has_ia_data = 1 if weeks_tracked >= 3 else 0
        if has_ia_data:
            ia_base = rng.uniform(10, 30) if declining else rng.uniform(20, 40)
            ia_latest = float(np.clip(ia_base + rng.normal(0, 3), 0, 40))
            ia_avg = float(np.clip(ia_base + rng.normal(0, 2), 0, 40))
        else:
            ia_latest = 0.0
            ia_avg = 0.0

        # Backlog
        backlog_current = int(rng.choice([0, 1, 2, 3, 4], p=[0.55, 0.20, 0.12, 0.08, 0.05]))
        backlog_growing = 1 if (declining and backlog_current > 0 and rng.random() < 0.6) else 0

        # Fee outstanding
        income_factor = 1 - (family_income / 100000)
        fee_outstanding = 1 if rng.random() < (0.1 + income_factor * 0.5) else 0

        # ── Compute dropout label ──
        risk = 0.0

        # Attendance slope is the most powerful signal
        if att_slope < -4:
            risk += 30
        elif att_slope < -2:
            risk += 18
        elif att_slope < 0:
            risk += 8
        else:
            risk -= 5  # improving = good signal

        # Current attendance
        if att_current < 50:
            risk += 25
        elif att_current < 60:
            risk += 15
        elif att_current < 75:
            risk += 5

        # Total drop
        if att_total_drop > 20:
            risk += 12
        elif att_total_drop > 10:
            risk += 6

        # IA performance
        if has_ia_data:
            if ia_latest < 15:
                risk += 20
            elif ia_latest < 22:
                risk += 10

        # Backlog
        risk += backlog_current * 8
        if backlog_growing:
            risk += 10

        # Fee
        if fee_outstanding:
            risk += 15

        # Background factors
        if family_income < 15000:
            risk += 12
        elif family_income < 30000:
            risk += 5
        if hs_grade < 60:
            risk += 8
        if home_loc == "Rural":
            risk += 6

        # Noise
        risk += rng.normal(0, 5)
        risk = float(np.clip(risk, 0, 100))

        dropout = 1 if risk >= 55 else 0

        records.append({
            "att_current": round(att_current, 2),
            "att_avg_4w": round(att_avg_4w, 2),
            "att_total_drop": round(att_total_drop, 2),
            "att_slope": round(att_slope, 3),
            "ia_latest": round(ia_latest, 2),
            "ia_avg": round(ia_avg, 2),
            "has_ia_data": has_ia_data,
            "backlog_current": backlog_current,
            "backlog_growing": backlog_growing,
            "fee_outstanding": fee_outstanding,
            "weeks_tracked": weeks_tracked,
            "Family_Income": family_income,
            "HighSchool_Grade": round(hs_grade, 1),
            "Home_Location": home_loc,
            "Dropout": dropout,
        })

    df = pd.DataFrame(records)
    drop_rate = df["Dropout"].mean()
    print(f"✅ engineered_training_data.csv: {len(df)} rows | Dropout rate: {drop_rate:.1%}")
    return df


# ─────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────

def generate_all():
    static_df = generate_static_data(10000)
    static_df.to_csv(DATA_DIR / "students_static.csv", index=False)

    dynamic_df = generate_engineered_data(10000)
    dynamic_df.to_csv(DATA_DIR / "engineered_training_data.csv", index=False)

    print(f"\n📁 Data saved to: {DATA_DIR}")
    print(f"   students_static.csv          → {len(static_df)} rows")
    print(f"   engineered_training_data.csv → {len(dynamic_df)} rows")


if __name__ == "__main__":
    generate_all()
