# EduGuard — Explainable Student Early Warning and Intervention Tracking

A final-year research prototype built with FastAPI, scikit-learn, SQLAlchemy and vanilla JavaScript.

**Validation status: synthetic demonstration only.** No real-world dropout accuracy, warning lead time or intervention effectiveness has been established. Scores are uncalibrated model outputs, not verified dropout probabilities. This project supports staff review; it must not make automated educational decisions.

## Working workflow

1. Admin imports admission CSV/JSON. Missing background fields remain missing.
2. Faculty imports weekly observations for their assigned class. IA scores are normalised using `IA_Max` (40 by default); displayed student marks are percentages.
3. One shared prediction service saves scores, input fingerprint, model version, data completeness and feature sensitivities. Weekly predictions require at least two observations. Incomplete profiles can use weekly-only scoring; insufficient data produces an unknown score.
4. Staff inspect observed trends and prediction evidence in the Risk Trend dialog.
5. Copilot reads the saved prediction and creates reviewable proposals with policy references. Repeated runs do not duplicate open proposals. Approval creates a pending intervention; it does not send external notifications.
6. Staff record an owner, due date, acceptance and follow-up evidence. Completion requires observations and a closure reason. Follow-up measurements remain separate from model inputs.
7. Students submit persisted help requests. Admins/counselors read and reply in the support inbox; students see the conversation and resolution status.
8. Evaluation compares attendance rules, admission-only, weekly-only and combined models on the same held-out cohort.

## Local setup

Python 3.12 is tested. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cd backend
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd frontend
python -m http.server 5500
```

Open http://localhost:5500/dashboard.html. API documentation: http://localhost:8000/docs.

First startup generates synthetic training data and trains versioned demo models; this can take a minute. Generated CSVs, databases and models are ignored by git. Startup preserves existing records and backfills missing v4 predictions without reseeding or deleting them.

`DEMO_MODE=true` (default) seeds demonstration accounts and synthetic weekly observations **only in an empty database**. Set `DEMO_MODE=false` to disable demo seeding; provision staff accounts separately. Existing demo accounts are not automatically removed. Use a separate database for authorised institutional data and set a strong `SECRET_KEY`.

| Demo role | Email | Password |
|---|---|---|
| Admin | admin@eduguard.com | admin123 |
| Faculty | faculty@eduguard.com | faculty123 |
| Counselor | counselor@eduguard.com | counselor123 |
| Student | student@eduguard.com | student123 |

## Upload formats

Admission columns:

```csv
id,name,class_name,semester,Family_Income,Scholarship,Education_Loan,Father_Occupation,Mother_Occupation,Parent_Education,Home_Location,HighSchool_Grade,Admission_Quota
DEMO-1,Example Student,CS-A,Semester 1,25000,No,No,Teacher,Homemaker,Graduate,Urban,75,Merit
```

`Admission_Quota` is retained for auditing but excluded from prediction features and synthetic label penalties. Income and other background variables can still act as proxies; omission of one sensitive feature does not establish fairness.

Weekly columns:

```csv
Student_ID,Week_Number,Attendance_Percentage,IA_Marks,IA_Max,Semester_Marks,Backlog_Count,Fee_Outstanding
DEMO-1,1,85,35,50,,0,No
DEMO-1,2,70,30,50,,1,Yes
```

`Week_Number` is an absolute index across the tracked enrolment, not reset each semester. Re-uploading the same student/week replaces that observation. Empty IA is allowed; missing backlog or fee status is rejected. Invalid/unauthorised rows are reported. Prediction failure rolls back the weekly import. A 5 MB upload limit applies.

## Evaluation and tests

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q
python -m app.ml.evaluate --synthetic --output evaluation-output
# After obtaining authorised, anonymised records with observed outcomes:
python -m app.ml.evaluate --data authorised_snapshots.csv --output evaluation-output-real
```

The evaluator saves metrics, held-out predictions and model artifacts. It uses older cohorts for training, the penultimate cohort for blend selection and the newest cohort for testing. Duplicate student IDs are rejected. Evaluation artifacts are separate from the deployed demonstration models.

See [evaluation protocol](docs/EVALUATION.md) for the dataset contract, research limitations and synthetic results, and [implementation notes](docs/IMPLEMENTATION.md) for migration and demo instructions.

## Policy configuration

`backend/app/policies/support.json` contains versioned **example** policies marked `approved: false`. Replace them with institution-approved text and accurate document, section, version, effective date and approval metadata. Retrieved references are shown on each Copilot ticket. An optional Anthropic integration can propose wording; staff remain responsible for reviewing the recommendation. No API key is needed for the deterministic fallback.

## Main components

- `services/prediction_service.py`: canonical scoring, abstention and sensitivity explanations.
- `services/access.py`: shared student/class access checks.
- `api/routes/upload.py`: validation, marks conversion and transactional import.
- `services/policy_service.py`: versioned local policy retrieval.
- `ml/evaluate.py`: cohort evaluation and baseline comparison.
- `tests/`: API isolation, prediction consistency, upload rollback and workflow tests.

SQLite is supported for the local prototype. Existing SQLite schemas receive additive columns; back up the database before upgrading. A production database migration, real-data validation, probability calibration, independent fairness review and institutional approval remain deployment prerequisites.

## Paired model training and current delivery status

Both v4 models train on the same student snapshots and binary outcome: `withdrawal_within_90_days_of_scoring`. They share a dataset fingerprint, cohort split and 90-day prediction horizon. The admission-feature model and weekly-feature model are two views of the same target. Scores remain uncalibrated; the bundled data is synthetic.

```bash
cd backend
python -m app.ml.train_models --data authorised_snapshots.csv --output candidate-models
```

Observed-data training requires `observed_at`, `followup_until`, `outcome_at`, `outcome_definition`, and `prediction_horizon_days` in addition to the evaluation feature columns. Negative outcomes require complete 90-day follow-up; positive withdrawal dates must fall inside that window. Candidate artifacts do not automatically replace the running models.

New admissions have `null` attendance and marks until recorded. Historical values of 100 cannot be distinguished automatically from genuine perfect scores; verify legacy imports before reuse.

Email/SMS delivery and scheduled suggestions are explicitly unavailable, disabled in the UI and rejected by the API if enabled. Copilot is manually run; support conversations are delivered through the portal. No external messages are sent.

Run frontend interaction checks from the repository root:

```bash
node frontend/tests/workflows.cjs
```

These execute the actual upload/request functions with mocked browser/network adapters. They check marks scale, original weeks, configured production URLs, failure handling and server-confirmed support requests; they are not visual browser tests.
