"""
app/ml/train_models.py
Trains BOTH models as described in the spec:
  Model 1 — Early Risk (Admission): RandomForestClassifier on students_static.csv
  Model 2 — Dynamic Risk (Weekly):  GradientBoostingClassifier on engineered_training_data.csv

Run standalone: python -m app.ml.train_models
Or called automatically on startup if models are missing.
"""
import logging
import os
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score

logger = logging.getLogger(__name__)

ML_DIR = Path(os.path.dirname(__file__))
DATA_DIR = ML_DIR / "data"
MODEL1_PATH = ML_DIR / "early_risk_model.pkl"
MODEL2_PATH = ML_DIR / "dynamic_risk_model.pkl"


# ─────────────────────────────────────────────────────────────
# MODEL 1 — Early Risk (Admission-time, RandomForest)
# ─────────────────────────────────────────────────────────────

def train_early_risk_model():
    csv = DATA_DIR / "students_static.csv"
    if not csv.exists():
        from app.ml.generate_datasets import generate_all
        generate_all()

    df = pd.read_csv(csv)
    # Only train on historical batches (never current batch)
    if "Batch" in df.columns:
        df = df[df["Batch"] < 2025]

    FEATURES = [
        "Family_Income", "Scholarship", "Education_Loan",
        "Father_Occupation", "Mother_Occupation", "Parent_Education",
        "Home_Location", "HighSchool_Grade", "Admission_Quota"
    ]

    cat_cols = ["Scholarship", "Education_Loan", "Father_Occupation",
                "Mother_Occupation", "Parent_Education", "Home_Location", "Admission_Quota"]
    num_cols = ["Family_Income", "HighSchool_Grade"]

    X = df[FEATURES]
    y = df["Dropout"]

    preprocessor = ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_cols),
        ("num", StandardScaler(), num_cols),
    ])

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("clf", RandomForestClassifier(
            n_estimators=300,
            max_depth=12,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ))
    ])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    logger.info("── Model 1 (Early Risk) ──────────────────")
    logger.info(f"\n{classification_report(y_test, y_pred, target_names=['No Dropout', 'Dropout'])}")
    logger.info(f"AUC-ROC: {roc_auc_score(y_test, y_proba):.4f}")

    payload = {
        "model": pipeline,
        "features": FEATURES,
        "cat_cols": cat_cols,
        "num_cols": num_cols,
    }
    joblib.dump(payload, MODEL1_PATH)
    logger.info(f"✅ Model 1 saved → {MODEL1_PATH}")
    return pipeline


# ─────────────────────────────────────────────────────────────
# MODEL 2 — Dynamic Risk (Weekly, GradientBoosting)
# ─────────────────────────────────────────────────────────────

def train_dynamic_risk_model():
    csv = DATA_DIR / "engineered_training_data.csv"
    if not csv.exists():
        from app.ml.generate_datasets import generate_all
        generate_all()

    df = pd.read_csv(csv)

    FEATURES = [
        "att_current", "att_avg_4w", "att_total_drop", "att_slope",
        "ia_latest", "ia_avg", "has_ia_data",
        "backlog_current", "backlog_growing",
        "fee_outstanding", "weeks_tracked",
        "Family_Income", "HighSchool_Grade", "Home_Location",
    ]

    cat_cols = ["Home_Location"]
    num_cols = [f for f in FEATURES if f != "Home_Location"]

    X = df[FEATURES]
    y = df["Dropout"]

    preprocessor = ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), cat_cols),
        ("num", StandardScaler(), num_cols),
    ])

    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("clf", GradientBoostingClassifier(
            n_estimators=400,
            max_depth=5,
            learning_rate=0.08,
            subsample=0.85,
            min_samples_leaf=10,
            random_state=42,
        ))
    ])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]

    logger.info("── Model 2 (Dynamic Risk) ────────────────")
    logger.info(f"\n{classification_report(y_test, y_pred, target_names=['No Dropout', 'Dropout'])}")
    logger.info(f"AUC-ROC: {roc_auc_score(y_test, y_proba):.4f}")

    payload = {
        "model": pipeline,
        "features": FEATURES,
        "cat_cols": cat_cols,
        "num_cols": num_cols,
    }
    joblib.dump(payload, MODEL2_PATH)
    logger.info(f"✅ Model 2 saved → {MODEL2_PATH}")
    return pipeline


# ─────────────────────────────────────────────────────────────
# PUBLIC — used by model.py / startup
# ─────────────────────────────────────────────────────────────

_early_model = None
_dynamic_model = None


def load_early_model():
    global _early_model
    if _early_model is not None:
        return _early_model
    if MODEL1_PATH.exists():
        logger.info(f"Loading Model 1 from {MODEL1_PATH}")
        _early_model = joblib.load(MODEL1_PATH)["model"]
    else:
        logger.info("Model 1 not found — training now...")
        _early_model = train_early_risk_model()
    return _early_model


def load_dynamic_model():
    global _dynamic_model
    if _dynamic_model is not None:
        return _dynamic_model
    if MODEL2_PATH.exists():
        logger.info(f"Loading Model 2 from {MODEL2_PATH}")
        _dynamic_model = joblib.load(MODEL2_PATH)["model"]
    else:
        logger.info("Model 2 not found — training now...")
        _dynamic_model = train_dynamic_risk_model()
    return _dynamic_model


def load_both_models():
    load_early_model()
    load_dynamic_model()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    # Generate data first
    from app.ml.generate_datasets import generate_all
    generate_all()

    # Train both
    train_early_risk_model()
    train_dynamic_risk_model()
    print("\n🎓 Both models trained successfully!")
