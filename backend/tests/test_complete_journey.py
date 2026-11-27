from io import BytesIO
from uuid import uuid4
import pandas as pd
import pytest
from openpyxl import load_workbook
from app.models.user import User
from app.models.student import Student
from app.models.support_request import SupportRequest
from app.core.security import hash_password
from app.ml.train_models import load_both_models, validate_outcomes, OUTCOME


def test_real_login_to_upload_support_followup_and_export(client, db):
    for role in ('admin', 'faculty', 'counselor'):
        db.get(User, role).hashed_password = hash_password('JourneyTest123!')
    db.commit()
    def login(email, role, password='JourneyTest123!'):
        response = client.post('/api/auth/login', json={'email': email, 'password': password, 'role': role})
        assert response.status_code == 200, response.text
        return {'Authorization': 'Bearer ' + response.json()['access_token']}
    admin, faculty, counselor = [login(r + '@example.com', r) for r in ('admin', 'faculty', 'counselor')]
    assert client.post('/api/auth/login', json={'email': 'admin@example.com', 'password': 'wrong', 'role': 'admin'}).status_code == 401
    admission = 'id,name,class_name,semester\nNEW1,New student,A,Semester 1\n'
    imported = client.post('/api/upload/admission', files={'file': ('admission.csv', admission)}, headers=admin)
    assert imported.status_code == 200, imported.text
    profile = client.get('/api/students/NEW1', headers=admin).json()
    assert profile['attendance'] is None and profile['marks'] is None and profile['risk_score'] is None
    provisioning = client.post('/api/users/students/common-password', json={'password': 'StudentTest123!'}, headers=admin)
    assert provisioning.status_code == 200, provisioning.text
    student = login('NEW1', 'student', 'StudentTest123!')
    weekly = 'Student_ID,Week_Number,Attendance_Percentage,IA_Marks,IA_Max,Backlog_Count,Fee_Outstanding\nNEW1,1,40,20,50,1,Yes\nNEW1,2,25,15,50,2,Yes\n'
    uploaded = client.post('/api/upload/weekly', files={'file': ('weekly.csv', weekly)}, headers=faculty)
    assert uploaded.status_code == 200, uploaded.text
    prediction = client.get('/api/students/NEW1/prediction', headers=student).json()
    assert prediction['risk_score'] is not None
    assert prediction['model_provenance']['prediction_horizon_days'] == 90
    assert client.get('/api/students/NEW1', headers=student).json()['marks'] == 30
    assert client.get('/api/students/B1', headers=student).status_code == 403
    key = str(uuid4())
    request = client.post('/api/support/requests', json={'category':'Academic', 'message':'Please help with missed classes.', 'submission_key':key}, headers=student)
    assert request.status_code == 201, request.text
    ident = request.json()['id']
    client.post('/api/support/requests', json={'category':'Academic', 'message':'Please help with missed classes.', 'submission_key':key}, headers=student)
    assert db.query(SupportRequest).count() == 1
    assert client.get('/api/support/requests', headers=counselor).json()[0]['id'] == ident
    assert client.get(f'/api/support/requests/{ident}', headers=faculty).status_code == 403
    response = client.post(f'/api/support/requests/{ident}/replies', json={'message':'Let us arrange academic support.', 'status':'In Progress'}, headers=counselor)
    assert response.status_code == 200, response.text
    assert client.get(f'/api/support/requests/{ident}', headers=student).json()['replies'][0]['message'] == 'Let us arrange academic support.'
    other_student = login('student@example.com', 'student', 'StudentTest123!')
    assert client.get(f'/api/support/requests/{ident}', headers=other_student).status_code == 403
    assert client.post(f'/api/support/requests/{ident}/replies', json={'message':'Override', 'status':'Resolved'}, headers=student).status_code == 403
    created = client.post('/api/interventions/', json={'student_id':'NEW1', 'type':'Academic Support'}, headers=counselor)
    assert created.status_code == 201, created.text
    iv_id = created.json()['id']
    assert client.put(f'/api/interventions/{iv_id}', json={'status':'Active'}, headers=counselor).status_code == 200
    assert client.put(f'/api/interventions/{iv_id}', json={'status':'Completed'}, headers=counselor).status_code == 422
    completed = client.put(f'/api/interventions/{iv_id}', json={'status':'Completed','closure_reason':'Plan reviewed','follow_up_observation':'Student attended the support session.','follow_up_attendance':65,'follow_up_marks':50}, headers=counselor)
    assert completed.status_code == 200, completed.text
    client.post(f'/api/support/requests/{ident}/replies', json={'message':'Support session completed; reply here if you need more help.', 'status':'Resolved'}, headers=counselor)
    assert client.get(f'/api/support/requests/{ident}', headers=student).json()['status'] == 'Resolved'
    export = client.get('/api/reports/interventions', headers=admin)
    workbook = load_workbook(BytesIO(export.content))
    rows = list(workbook.active.values)
    assert any(row[0] == 'NEW1' and 'Student attended the support session.' in row for row in rows)
    assert client.get('/api/reports/high-risk-summary', headers=admin).content.startswith(b'%PDF')
    assert client.get('/api/reports/interventions', headers=student).status_code == 403


def test_notification_unavailability_is_enforced(client, headers):
    response = client.get('/api/settings/', headers=headers('admin'))
    assert response.json()['notification_delivery_available'] is False
    assert response.json()['email_notifications'] is False
    assert client.put('/api/settings/notifications', headers=headers('admin'), json={'email_notifications': True, 'sms_alerts': False, 'ai_auto_suggestions': False}).status_code == 409


def test_both_live_models_share_outcome_and_students():
    early, dynamic = load_both_models()
    assert early.eduguard_metadata == dynamic.eduguard_metadata
    assert early.eduguard_metadata['outcome_definition'] == OUTCOME
    assert early.eduguard_metadata['prediction_horizon_days'] == 90
    assert early.eduguard_metadata['calibrated'] is False


def test_censored_or_contradictory_outcomes_rejected():
    data = pd.DataFrame([{'observed_at':'2025-01-01','followup_until':'2025-01-10','outcome_at':None,'outcome_definition':OUTCOME,'prediction_horizon_days':90,'Dropout':0}])
    with pytest.raises(ValueError, match='complete 90-day'):
        validate_outcomes(data)
    data['followup_until'] = '2025-05-01'
    validate_outcomes(data)
    data['outcome_at'] = '2025-02-01'
    with pytest.raises(ValueError, match='contradicts'):
        validate_outcomes(data)
