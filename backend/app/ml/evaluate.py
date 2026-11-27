"""Reproducible cohort-held-out comparison; never implies synthetic accuracy is real."""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, brier_score_loss, confusion_matrix
from app.services.prediction_service import EARLY_FIELDS

EARLY = list(EARLY_FIELDS)
DYNAMIC = ["att_current", "att_avg_4w", "att_total_drop", "att_slope", "ia_latest", "ia_avg", "has_ia_data", "backlog_current", "backlog_growing", "fee_outstanding", "weeks_tracked"]
CATEGORICAL = [x for x in EARLY if x not in ("Family_Income", "HighSchool_Grade")]


def split_cohorts(df):
    required = set(EARLY + DYNAMIC + ["student_id", "cohort", "Dropout"])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if df.student_id.isna().any() or df.student_id.duplicated().any():
        raise ValueError("Provide one prediction-time snapshot per unique student; duplicate student IDs could leak outcomes")
    if df.cohort.isna().any() or not set(df.Dropout.unique()) <= {0, 1}:
        raise ValueError("Cohort and binary observed Dropout outcome are required")
    cohorts = sorted(df.cohort.unique())
    if len(cohorts) < 3:
        raise ValueError("At least three ordered cohorts are needed for train/validation/test")
    parts = (df[df.cohort < cohorts[-2]], df[df.cohort == cohorts[-2]], df[df.cohort == cohorts[-1]])
    if any(p.Dropout.nunique() < 2 for p in parts):
        raise ValueError("Every split needs both outcomes to evaluate discrimination")
    if "observed_at" in df and "outcome_at" in df:
        observation = pd.to_datetime(df.observed_at, errors="raise", utc=True)
        outcome = pd.to_datetime(df.outcome_at, errors="raise", utc=True)
        if observation.isna().any() or (outcome.notna() & (observation >= outcome)).any():
            raise ValueError("Features must be observed strictly before the outcome date")
    return parts


def build_model(features, dynamic=False):
    cats = [c for c in features if c in CATEGORICAL]
    nums = [c for c in features if c not in cats]
    prep = ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), nums),
        ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore", sparse_output=False)), cats),
    ])
    clf = GradientBoostingClassifier(n_estimators=80, max_depth=3, random_state=42) if dynamic else RandomForestClassifier(n_estimators=100, min_samples_leaf=5, class_weight="balanced", random_state=42, n_jobs=1)
    return make_pipeline(prep, clf)


def metrics(y, probability, threshold=.7):
    pred = probability >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"threshold": threshold, "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)), "f1": float(f1_score(y, pred, zero_division=0)),
        "pr_auc_average_precision": float(average_precision_score(y, probability)),
        "brier_score": float(brier_score_loss(y, probability)), "false_alerts": int(fp),
        "missed_outcomes": int(fn), "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}}


def evaluate(df, output, provenance):
    train, validation, test = split_cohorts(df)
    models = [build_model(EARLY), build_model(DYNAMIC, True)]
    scores = []
    for model, features in zip(models, (EARLY, DYNAMIC)):
        model.fit(train[features], train.Dropout)
        scores.append((model.predict_proba(validation[features])[:, 1], model.predict_proba(test[features])[:, 1]))
    ve, te = scores[0]
    vd, td = scores[1]
    schedule = lambda p: np.where(p.weeks_tracked <= 2, .6, np.where(p.weeks_tracked <= 7, .4, .2))
    candidates = {"scheduled": (schedule(validation), schedule(test))}
    candidates.update({f"early_weight_{w}": (w, w) for w in (0., .2, .4, .6, .8, 1.)})
    validation_losses = {name: float(brier_score_loss(validation.Dropout, vw * ve + (1 - vw) * vd)) for name, (vw, _) in candidates.items()}
    selected = min(validation_losses, key=validation_losses.get)
    tw = candidates[selected][1]
    predictions = {"attendance_threshold": (test.att_current.to_numpy() < 75).astype(float),
        "admission_only": te, "weekly_only": td, "combined_selected": tw * te + (1 - tw) * td,
        "combined_original_schedule": schedule(test) * te + (1 - schedule(test)) * td}
    report = {
        "provenance": provenance, "validation_status": "synthetic_only" if provenance == "synthetic" else "held_out_dataset_evaluation_not_external_validation",
        "dataset_sha256": hashlib.sha256(df.to_csv(index=False).encode()).hexdigest(),
        "seed": 42, "split": {k: {"rows": len(p), "cohorts": [str(x) for x in sorted(p.cohort.unique())]} for k, p in zip(("train", "validation", "test"), (train, validation, test))},
        "selected_blend": selected, "validation_brier": validation_losses,
        "results": {name: metrics(test.Dropout, np.asarray(pred)) for name, pred in predictions.items()},
        "limitations": ["Uncalibrated scores; Brier measures probability error but does not establish calibration.",
            "One snapshot per student; warning lead time requires dated longitudinal follow-up.",
            "Observed outcomes do not establish intervention effectiveness.",
            "Evaluation models are saved separately and are not automatically deployed."],
    }
    if "audit_group" in test:
        report["subgroup_results"] = {str(group): metrics(rows.Dropout, np.asarray(predictions["combined_selected"])[test.index.get_indexer(rows.index)]) for group, rows in test.groupby("audit_group") if rows.Dropout.nunique() == 2}
        report["subgroup_note"] = "Only groups with both outcomes are reported; small samples are inconclusive."
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.json").write_text(json.dumps(report, indent=2))
    for name, model in zip(("admission", "weekly"), models):
        joblib.dump(model, output / f"{name}.joblib")
    test_out = test[["student_id", "cohort", "Dropout"]].copy()
    for name, pred in predictions.items():
        test_out[name] = pred
    test_out.to_csv(output / "test_predictions.csv", index=False)
    return report


def synthetic_demo(n=1200):
    from app.ml.generate_datasets import generate_static_data, generate_engineered_data
    static, dynamic = generate_static_data(n), generate_engineered_data(n)
    # Paired snapshots use one shared simulated outcome; never combine unrelated labels.
    df = static[EARLY].copy()
    for col in DYNAMIC + ["Dropout"]:
        df[col] = dynamic[col]
    df["student_id"] = [f"SYN-{i:05}" for i in range(n)]
    df["cohort"] = np.repeat([2022, 2023, 2024], [n // 3, n // 3, n - 2 * (n // 3)])
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("evaluation-output"))
    args = parser.parse_args()
    if bool(args.data) == args.synthetic:
        parser.error("Choose exactly one: --data authorised.csv OR --synthetic")
    df = synthetic_demo() if args.synthetic else pd.read_csv(args.data)
    if args.data:
        from app.ml.train_models import validate_outcomes
        validate_outcomes(df)
    report = evaluate(df, args.output, "synthetic" if args.synthetic else "user_supplied_observed_outcomes")
    print(json.dumps({"validation_status": report["validation_status"], "selected_blend": report["selected_blend"], "results": report["results"]}, indent=2))


if __name__ == "__main__":
    main()
