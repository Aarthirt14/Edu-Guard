"""Train both feature views on the SAME students, outcome and 90-day horizon."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import pandas as pd

ML_DIR = Path(__file__).parent
MODEL1_PATH = ML_DIR / "early_risk_v4.pkl"
MODEL2_PATH = ML_DIR / "dynamic_risk_v4.pkl"
OUTCOME = "withdrawal_within_90_days_of_scoring"
_early_model = _dynamic_model = None


def validate_outcomes(df):
    """Reject ambiguous/censored labels instead of treating enrolled students as negatives."""
    required = {"Dropout", "observed_at", "followup_until", "outcome_at", "outcome_definition", "prediction_horizon_days"}
    if not required <= set(df):
        raise ValueError(f"Missing outcome provenance: {sorted(required - set(df))}")
    if set(df.outcome_definition) != {OUTCOME} or set(df.prediction_horizon_days) != {90}:
        raise ValueError("Both models require the same withdrawal outcome and 90-day horizon")
    observed = pd.to_datetime(df.observed_at, utc=True, errors="raise")
    followup = pd.to_datetime(df.followup_until, utc=True, errors="raise")
    outcome = pd.to_datetime(df.outcome_at, utc=True, errors="raise")
    end = observed + pd.Timedelta(days=90)
    positive = df.Dropout == 1
    if observed.isna().any() or followup.isna().any() or (followup < observed).any():
        raise ValueError("Observation and follow-up dates are required")
    if ((~positive) & (followup < end)).any():
        raise ValueError("Negative labels require complete 90-day follow-up")
    if (positive & (outcome.isna() | (outcome <= observed) | (outcome > end) | (outcome > followup))).any():
        raise ValueError("Positive outcomes must occur within the observed 90-day horizon")
    if ((~positive) & outcome.notna() & (outcome > observed) & (outcome <= end)).any():
        raise ValueError("Negative label contradicts a withdrawal in the prediction horizon")


def train_bundle(df=None, output=ML_DIR):
    from app.ml.evaluate import synthetic_demo, split_cohorts, build_model, EARLY, DYNAMIC, CATEGORICAL, metrics
    synthetic = df is None
    if synthetic:
        df = synthetic_demo(3000)
    else:
        validate_outcomes(df)
    train, validation, test = split_cohorts(df)
    digest = hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
    metadata = {"version": "v4-" + digest[:12], "dataset_sha256": digest,
        "outcome_definition": OUTCOME, "prediction_horizon_days": 90,
        "training_source": "synthetic" if synthetic else "user_supplied_observed_outcomes",
        "validation_status": "synthetic_demo_not_real_world_validated" if synthetic else "held_out_cohort_not_external_validation",
        "split": {name: [str(x) for x in sorted(part.cohort.unique())] for name, part in zip(("train", "validation", "test"), (train, validation, test))},
        "calibrated": False, "test_metrics": {}}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    models = []
    for name, features, dynamic in (("early", EARLY, False), ("dynamic", DYNAMIC, True)):
        model = build_model(features, dynamic)
        model.fit(train[features], train.Dropout)
        model.eduguard_reference = {col: str(train[col].mode().iloc[0]) if col in CATEGORICAL else float(train[col].median()) for col in features}
        metadata["test_metrics"][name] = metrics(test.Dropout, model.predict_proba(test[features])[:, 1])
        models.append(model)
    # Both artifacts carry the identical target, provenance and dataset fingerprint.
    for name, model in zip(("early", "dynamic"), models):
        model.eduguard_metadata = metadata
        path = output / ("early_risk_v4.pkl" if name == "early" else "dynamic_risk_v4.pkl")
        temporary = path.with_suffix(".tmp")
        joblib.dump({"model": model, "metadata": metadata}, temporary)
        temporary.replace(path)
    (output / "training-v4.metadata.json").write_text(json.dumps(metadata, indent=2))
    return tuple(models)


def load_both_models():
    global _early_model, _dynamic_model
    if _early_model is None or _dynamic_model is None:
        if MODEL1_PATH.exists() and MODEL2_PATH.exists():
            first, second = joblib.load(MODEL1_PATH), joblib.load(MODEL2_PATH)
            if first["metadata"] != second["metadata"]:
                raise RuntimeError("Model pair provenance differs; retrain both as one bundle")
            _early_model, _dynamic_model = first["model"], second["model"]
        else:
            _early_model, _dynamic_model = train_bundle()
    return _early_model, _dynamic_model


def load_early_model():
    return load_both_models()[0]


def load_dynamic_model():
    return load_both_models()[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, help="Authorised paired snapshots with verified outcome provenance")
    parser.add_argument("--output", type=Path, default=ML_DIR / "candidate-models")
    args = parser.parse_args()
    train_bundle(pd.read_csv(args.data) if args.data else None, args.output)
    print(f"Saved paired candidate models to {args.output}; production activation is separate.")
