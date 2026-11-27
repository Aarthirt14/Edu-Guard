import numpy as np
import pytest
from app.models.student import Student, WeeklyRecord, RiskHistory
from app.models.intervention import Intervention
from app.services.prediction_service import refresh_prediction
from app.services.copilot_service import _predict_risk_payload
from app.ml.evaluate import synthetic_demo, split_cohorts, evaluate

class ObservedModel:
    eduguard_reference = {"att_current": 80, "att_slope": 0}
    def predict_proba(self, frame):
        p = np.clip(1 - frame.att_current.to_numpy() / 100, 0, 1)
        return np.column_stack([1 - p, p])

@pytest.fixture
def models(monkeypatch):
    monkeypatch.setattr("app.services.prediction_service.load_dynamic_model", lambda: ObservedModel())

@pytest.mark.parametrize("path", ["/api/students/B1", "/api/students/B1/history", "/api/students/B1/risk-trend", "/api/students/B1/prediction", "/api/interventions/B1/timeline"])
def test_student_cannot_read_peer(client, headers, path):
    assert client.get(path, headers=headers("student")).status_code == 403

def test_faculty_scope_and_student_listing(client, headers):
    assert client.put("/api/students/B1", json={"marks": 10}, headers=headers("faculty")).status_code == 403
    assert client.get("/api/students/high-risk", headers=headers("student")).status_code == 403
    assert client.get("/api/students/A1", headers=headers("student")).status_code == 200
    assert client.post("/api/analytics/ai-chat", json={"message": "list students"}, headers=headers("student")).status_code == 403

def test_missing_data_abstains(db):
    s = db.get(Student, "A1")
    result = refresh_prediction(db, s)
    assert result["risk_score"] is None and result["mode"] == "insufficient_data"
    assert "confidence" not in result
    assert _predict_risk_payload([s]) == []

def upload(client, headers, text):
    return client.post("/api/upload/weekly", files={"file": ("weekly.csv", text, "text/csv")}, headers=headers("faculty"))

HEADER = "Student_ID,Week_Number,Attendance_Percentage,IA_Marks,IA_Max,Backlog_Count,Fee_Outstanding\n"

def test_upload_consistency_marks_and_idempotency(client, headers, db, models):
    data = HEADER + "A1,1,80,35,50,0,No\nA1,3,60,30,50,1,Yes\n"
    response = upload(client, headers, data)
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 2
    student = db.get(Student, "A1")
    assert student.marks == 60
    assert student.prediction["weekly_features"]["att_slope"] == pytest.approx(-10)
    assert student.risk_score == 40
    assert _predict_risk_payload([student])[0]["risk_score"] == student.risk_score
    history = db.query(RiskHistory).count()
    again = upload(client, headers, data)
    assert again.json()["updated"] == 2
    assert db.query(RiskHistory).count() == history and db.query(WeeklyRecord).count() == 2
    assert client.get("/api/students/A1/prediction", headers=headers("student")).json()["risk_score"] == 40

@pytest.mark.parametrize("row", ["B1,1,80,20,40,0,No", "A1,1,nan,20,40,0,No", "A1,1,80,41,40,0,No", "A1,1.5,80,20,40,0,No", "A1,1,80,20,40,0,maybe"])
def test_invalid_or_unauthorised_rows_do_not_write(client, headers, db, row):
    response = upload(client, headers, HEADER + row)
    assert response.status_code == 200 and response.json()["errors"]
    assert db.query(WeeklyRecord).count() == 0

def test_prediction_failure_rolls_back_upload(client, headers, db, monkeypatch):
    def fail(*args):
        raise RuntimeError("model missing")
    monkeypatch.setattr("app.api.routes.upload.process_weekly_upload_for_student", fail)
    assert upload(client, headers, HEADER + "A1,1,80,20,40,0,No").status_code == 503
    assert db.query(WeeklyRecord).count() == 0

def test_intervention_acceptance_and_evidence(client, headers, db):
    created = client.post("/api/interventions/", json={"student_id": "A1", "type": "Mentorship"}, headers=headers("admin"))
    assert created.status_code == 201, created.text
    ident = created.json()["id"]
    active = client.put(f"/api/interventions/{ident}", json={"status": "Active"}, headers=headers("counselor"))
    assert active.json()["accepted_at"]
    assert client.put(f"/api/interventions/{ident}", json={"status": "Completed"}, headers=headers("admin")).status_code == 422
    done = client.put(f"/api/interventions/{ident}", json={"status": "Completed", "closure_reason": "Plan reviewed", "follow_up_observation": "Attendance increased from 80 to 85", "follow_up_attendance": 85}, headers=headers("admin"))
    assert done.status_code == 200, done.text
    assert done.json()["baseline_attendance"] == 80
    assert db.get(Intervention, ident).follow_up_attendance == 85

def test_cohort_split_rejects_student_leakage():
    data = synthetic_demo(180)
    data.loc[1, "student_id"] = data.loc[0, "student_id"]
    with pytest.raises(ValueError, match="duplicate"):
        split_cohorts(data)

def test_evaluation_same_test_cohort_and_saved_metrics(tmp_path):
    report = evaluate(synthetic_demo(300), tmp_path, "synthetic")
    assert report["validation_status"] == "synthetic_only"
    assert report["split"]["test"]["cohorts"] == ["2024"]
    assert len(report["results"]) == 5
    assert (tmp_path / "test_predictions.csv").exists()
    assert all(sum(v["confusion_matrix"].values()) == 100 for v in report["results"].values())


def test_copilot_requires_approval_and_deduplicates(client, headers, db):
    student = db.get(Student, "A1")
    student.risk_score = 90
    student.prediction = {"risk_score": 90, "risk_level": "high"}
    db.commit()
    first = client.post('/api/copilot/runs', json={}, headers=headers('admin'))
    assert first.status_code == 200, first.text
    assert first.json()['actions_created'] == 1
    assert db.query(Intervention).count() == 0
    detail = client.get(f"/api/copilot/runs/{first.json()['id']}", headers=headers('admin')).json()
    ticket = detail['tickets'][0]
    again = client.post('/api/copilot/runs', json={}, headers=headers('admin'))
    assert again.json()['actions_created'] == 0
    approved = client.post(f"/api/copilot/tickets/{ticket['id']}/approve", headers=headers('counselor'))
    assert approved.status_code == 200, approved.text
    assert db.query(Intervention).count() == 1
    assert client.post(f"/api/copilot/tickets/{ticket['id']}/approve", headers=headers('admin')).status_code == 409


def test_own_profile_and_no_fabricated_snapshot_score(client, headers):
    assert client.get('/api/students/me/profile', headers=headers('student')).json()['id'] == 'A1'
    result = client.post('/api/students/predict', json={'attendance': 20, 'marks': 10}, headers=headers('admin'))
    assert result.status_code == 200 and result.json()['risk_score'] is None
    assert 'confidence' not in result.json()
