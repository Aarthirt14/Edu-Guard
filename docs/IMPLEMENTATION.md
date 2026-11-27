# Implementation and demonstration notes

## Upgrading

Back up the SQLite database. Startup adds prediction JSON fields, Copilot policy references and intervention follow-up columns, then backfills legacy students using actual saved records. Legacy scores without enough data become unknown. Existing risk-history entries remain for audit; new entries contain prediction metadata. Existing demo data is preserved, not purged.

The old `/api/students/predict` snapshot endpoint now returns `risk_score: null` and guidance to upload adequate data. A single attendance/marks snapshot cannot reconstruct a trend or family profile. Consumers must handle null scores. Fetch `/api/students/{id}/prediction` for the saved authoritative result.

Student.marks is always a percentage. WeeklyRecord.ia_marks remains out of 40 for compatibility with model training. `IA_Max` converts uploads to this canonical scale. Historical imports with unknown original scales require manual verification; conversion cannot recover missing provenance.

## Demonstration

1. Sign in as admin and inspect a seeded high-risk student's Risk Trend dialog. It shows observations, data completeness, model version and feature sensitivities.
2. Sign in as faculty. Upload two weekly records for CS-A. Attempt a different class to demonstrate rejected access.
3. Run the Copilot as admin. Inspect cited example policies and approve one proposal. Repeat a run to show open-proposal deduplication.
4. Open Interventions → Review / follow up. Set owner and due date, accept the case, then record measurements and a closure reason. Completion without follow-up evidence is rejected.
5. Run the evaluator and discuss the comparison honestly, including cases where the original blend underperforms weekly-only prediction.

## Explanation semantics

For each feature, replace its value with a training-set reference (median or mode), recompute the model and report the weighted score difference. These are local model sensitivities. Correlated features and interactions mean differences are not additive. They are not causal claims, SHAP values or guarantees that changing a feature will change a student's outcome.

## Access model

Students can read only their explicitly linked record. Faculty are restricted to their assigned class, including weekly uploads and bulk student account password operations. Admins and counselors have institution-wide read access under this prototype's policy. Aggregate student-data chat is restricted to admin/counselor accounts. A counselor may only complete their own counseling session; admins may complete any.

## Boundaries

Copilot proposals require staff approval and do not send email, Slack, n8n or guardian messages. The sample policies are not institution-approved. Follow-up notes are evidence of observations, not proof of effectiveness. Automated deployment, live college imports, institutional policy approval and real-world evaluation were not performed.

## Verification performed

- 23 automated regression checks pass, including student isolation, faculty scope, marks normalisation, sparse-week slope calculation, upload idempotency and rollback, abstention, staff approval, ticket deduplication, follow-up closure and cohort splitting.
- Actual demo model training, startup, login, student prediction, intervention listing, analytics and Copilot API smoke checks passed.
- Synthetic cohort evaluation completed; results are in `synthetic-evaluation.json`.
- JavaScript syntax and Python compilation checks passed; pip reported no broken requirements.
- Visual browser verification could not run: the installed Chromium launcher has no binary and the browser download was blocked. Review the Risk Trend evidence panel, Copilot approval button and follow-up dialog in a browser before merging/deploying.

## Connected journey verification

The complete API journey test uses actual password authentication and actual v4 model inference: admin admission import → student account provisioning → faculty weekly upload → student prediction → student help request → counselor reply → intervention acceptance → observed follow-up → completion → Excel/PDF export. It checks peer/student restrictions, rejected login and incomplete closure. Frontend interaction checks verify the configured deployed URL, preservation of IA_Max and row week, upload error handling, and request text retention after a network failure. Requests are visible to the student and admin/counselor support staff; faculty cannot read private conversations.

Notification delivery is explicitly unavailable. Scheduled suggestions are disabled; Copilot remains manual. Historical imported marks with unknown scale or default 100 values still require verification. The legacy shared-password account provisioning flow remains suitable only for demonstrations; individual account onboarding is needed before real deployment.
