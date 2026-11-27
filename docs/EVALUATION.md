# Evaluation protocol

Research question: does combining admission information and weekly trends improve early warning over a simple attendance threshold or either model alone?

## Data contract

Use anonymised authorised historical records with a documented outcome definition and prediction date. The evaluator expects one snapshot per unique `student_id`, numeric ordered `cohort`, binary observed `Dropout` (0 or 1), plus these columns:

- Admission: Family_Income, Scholarship, Education_Loan, Father_Occupation, Mother_Occupation, Parent_Education, Home_Location, HighSchool_Grade.
- Weekly: att_current, att_avg_4w, att_total_drop, att_slope, ia_latest, ia_avg, has_ia_data, backlog_current, backlog_growing, fee_outstanding, weeks_tracked.
- Required for observed data: observed_at, followup_until, outcome_at (blank for no withdrawal), outcome_definition=`withdrawal_within_90_days_of_scoring`, prediction_horizon_days=90. Optional audit_group enables subgroup reporting.

IA features are out of 40. Attendance and school grade are percentages. Features must reflect only information available at prediction time. Do not include future marks, future attendance or outcome-derived fields. Distinguish graduation, transfer and confirmed withdrawal in the source data; define which outcome is being studied before producing the binary label. A currently enrolled student without completed follow-up is not automatically a negative outcome.

At least three cohorts are required, each split containing both outcomes. Older cohorts train the models; the penultimate cohort selects blend weights by Brier score; the latest cohort is untouched until testing. Imputation and categorical encoding are fitted only on training data. IDs and admission quota are not model inputs. The fixed alert threshold is 0.7; the attendance baseline alerts below 75%.

## Outputs

`metrics.json` records dataset hash, seed, split sizes, chosen blend, precision, recall, F1, average precision (PR-AUC summary), Brier score, false alerts and confusion matrices. `test_predictions.csv` allows error inspection. Model artifacts are saved separately; the evaluation command does not switch the running application to these models.

The original scheduled blend is reported alongside the validation-selected blend. Choosing a zero admission weight is an acceptable result; do not claim the combined system is better unless the held-out evidence supports it.

## Synthetic smoke experiment

The checked-in `synthetic-evaluation.json` records a reproducible 1,200-student simulation with 400 students in each split. It tests the evaluation machinery only. Simulated admission attributes are independently sampled from weekly trajectories, so it does not provide a realistic test of the added value of admission information. Both models are trained against the same simulated outcome for this comparison.

The v4 live demonstration models now train on the same paired dataset and shared synthetic outcome, with a declared 90-day horizon and identical provenance metadata. No synthetic simulation establishes real-world validity or probability calibration. Observed-data training validates outcome timing and requires full follow-up for negative labels.

## Still requiring evidence

- Real, authorised historical outcomes and an external cohort.
- Reliability/calibration curves and independently evaluated calibration if probabilities will be displayed.
- Longitudinal snapshots with dated outcomes to measure earliest correct warning and warning lead time. The current evaluator supports one snapshot per student and deliberately does not invent this metric.
- Subgroup sample sizes and false-positive/false-negative rates. Results for tiny groups are not proof of fairness.
- Staff usability assessment and a controlled intervention study. Observed pre/post improvements do not prove causation.

Never report simulation metrics as college performance or claim prevented dropouts from reduced model scores.
