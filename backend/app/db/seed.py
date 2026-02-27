# ============================================================
# app/db/seed.py — Seed DB with users + students from app.js
# ============================================================
import logging
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.student import Student, RiskHistory
from app.models.intervention import Intervention, InterventionType, InterventionStatus, InterventionOutcome, TimelineEvent
from app.core.security import hash_password
from app.ml.model import predict_risk
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DEMO_STUDENT_IDS = [
    "STU-1024", "STU-1087", "STU-1132", "STU-1205", "STU-1289", "STU-1301", "STU-1356",
    "STU-1422", "STU-1478", "STU-1503", "STU-1567", "STU-1612", "STU-1650", "STU-1701",
]


def seed_users(db: Session):
    existing = db.query(User).first()
    if existing:
        return

    users = [
        User(id="admin1", email="admin@eduguard.com",
             hashed_password=hash_password("admin123"),
             name="Dr. Arun Kumar", role=UserRole.admin),
        User(id="faculty1", email="faculty@eduguard.com",
             hashed_password=hash_password("faculty123"),
             name="Prof. Meena", role=UserRole.faculty, assigned_class="CS-A"),
        User(id="counselor1", email="counselor@eduguard.com",
             hashed_password=hash_password("counselor123"),
             name="Dr. Ravi", role=UserRole.counselor),
        User(id="student1", email="student@eduguard.com",
             hashed_password=hash_password("student123"),
             name="Arjun", role=UserRole.student),
    ]
    db.add_all(users)
    db.commit()
    logger.info("✅ Seeded users")


def seed_students(db: Session):
    existing = db.query(Student).first()
    if existing:
        return

    # Exact data from your app.js
    raw_students = [
        {"id": "STU-1024", "name": "Rahul Verma",   "class_name": "CS-A", "semester": "Semester 4", "attendance": 48, "marks": 32, "financial": True,  "family": False},
        {"id": "STU-1087", "name": "Priya Singh",   "class_name": "CS-A", "semester": "Semester 3", "attendance": 52, "marks": 38, "financial": False, "family": True},
        {"id": "STU-1132", "name": "Vikram Patel",  "class_name": "EC-A", "semester": "Semester 5", "attendance": 55, "marks": 41, "financial": True,  "family": False},
        {"id": "STU-1205", "name": "Anita Desai",   "class_name": "CS-B", "semester": "Semester 4", "attendance": 50, "marks": 35, "financial": False, "family": True},
        {"id": "STU-1289", "name": "Suresh Kumar",  "class_name": "ME-A", "semester": "Semester 6", "attendance": 58, "marks": 44, "financial": True,  "family": False},
        {"id": "STU-1301", "name": "Deepa Nair",    "class_name": "CS-A", "semester": "Semester 3", "attendance": 54, "marks": 40, "financial": False, "family": False},
        {"id": "STU-1356", "name": "Arjun Menon",   "class_name": "CE-A", "semester": "Semester 2", "attendance": 60, "marks": 42, "financial": True,  "family": True},
        {"id": "STU-1422", "name": "Kavitha Raj",   "class_name": "EC-A", "semester": "Semester 4", "attendance": 56, "marks": 39, "financial": False, "family": False},
        {"id": "STU-1478", "name": "Mohan Das",     "class_name": "CS-A", "semester": "Semester 5", "attendance": 62, "marks": 43, "financial": True,  "family": False},
        {"id": "STU-1503", "name": "Fatima Khan",   "class_name": "CS-B", "semester": "Semester 3", "attendance": 58, "marks": 37, "financial": False, "family": True},
        {"id": "STU-1567", "name": "Rajesh Iyer",   "class_name": "ME-A", "semester": "Semester 4", "attendance": 53, "marks": 36, "financial": True,  "family": False},
        {"id": "STU-1612", "name": "Sneha Reddy",   "class_name": "CS-A", "semester": "Semester 2", "attendance": 59, "marks": 45, "financial": False, "family": True},
        {"id": "STU-1650", "name": "Amit Joshi",    "class_name": "CE-A", "semester": "Semester 6", "attendance": 51, "marks": 33, "financial": True,  "family": True},
        {"id": "STU-1701", "name": "Lakshmi Bhat",  "class_name": "EC-A", "semester": "Semester 3", "attendance": 57, "marks": 40, "financial": False, "family": False},
    ]

    for s in raw_students:
        sem_num = int(s["semester"].split()[-1])
        pred = predict_risk(s["attendance"], s["marks"], s["financial"], s["family"], sem_num)
        trend = "up" if pred["risk_score"] >= 75 else "down"

        student = Student(
            id=s["id"],
            name=s["name"],
            class_name=s["class_name"],
            semester=s["semester"],
            attendance=s["attendance"],
            marks=s["marks"],
            has_financial_issue=s["financial"],
            has_family_issue=s["family"],
            risk_score=pred["risk_score"],
            risk_trend=trend,
        )
        db.add(student)

        # Add a few history points
        for i in range(3):
            db.add(RiskHistory(
                student_id=s["id"],
                risk_score=max(0, pred["risk_score"] - (i * 5)),
                recorded_at=datetime.utcnow() - timedelta(weeks=i * 2)
            ))

    db.commit()
    logger.info("✅ Seeded students with ML-computed risk scores")


def seed_interventions(db: Session):
    existing = db.query(Intervention).first()
    if existing:
        return

    raw = [
        {"sid": "STU-1024", "type": InterventionType.counseling,        "by": "Dr. Arun Kumar",   "status": InterventionStatus.active,     "outcome": InterventionOutcome.improving},
        {"sid": "STU-1024", "type": InterventionType.financial_support, "by": "Admin Office",     "status": InterventionStatus.pending,    "outcome": InterventionOutcome.none},
        {"sid": "STU-1132", "type": InterventionType.academic_support,  "by": "Prof. Ravi Gupta", "status": InterventionStatus.active,     "outcome": InterventionOutcome.stable},
        {"sid": "STU-1289", "type": InterventionType.counseling,        "by": "Dr. Meena Sharma", "status": InterventionStatus.active,     "outcome": InterventionOutcome.improving},
        {"sid": "STU-1422", "type": InterventionType.mentorship,        "by": "Dr. Arun Kumar",   "status": InterventionStatus.active,     "outcome": InterventionOutcome.stable},
        {"sid": "STU-1087", "type": InterventionType.family_outreach,   "by": "Dr. Meena Sharma", "status": InterventionStatus.pending,    "outcome": InterventionOutcome.none},
        {"sid": "STU-1503", "type": InterventionType.academic_support,  "by": "Prof. Ravi Gupta", "status": InterventionStatus.completed,  "outcome": InterventionOutcome.improved},
        {"sid": "STU-1612", "type": InterventionType.counseling,        "by": "Dr. Meena Sharma", "status": InterventionStatus.completed,  "outcome": InterventionOutcome.improved},
        {"sid": "STU-1301", "type": InterventionType.financial_support, "by": "Admin Office",     "status": InterventionStatus.pending,    "outcome": InterventionOutcome.none},
        {"sid": "STU-1205", "type": InterventionType.counseling,        "by": "Dr. Arun Kumar",   "status": InterventionStatus.completed,  "outcome": InterventionOutcome.improved},
    ]

    for r in raw:
        iv = Intervention(
            student_id=r["sid"],
            type=r["type"],
            assigned_by=r["by"],
            status=r["status"],
            outcome=r["outcome"],
        )
        db.add(iv)
        db.flush()

        # Seed a timeline event per intervention
        db.add(TimelineEvent(
            intervention_id=iv.id,
            student_id=r["sid"],
            event_type=r["type"].value,
            description=f"{r['type'].value} assigned by {r['by']}. Status: {r['status'].value}.",
        ))

    db.commit()
    logger.info("✅ Seeded interventions + timeline events")


def purge_demo_seed_data(db: Session):
    timeline_deleted = db.query(TimelineEvent).filter(TimelineEvent.student_id.in_(DEMO_STUDENT_IDS)).delete(synchronize_session=False)
    interventions_deleted = db.query(Intervention).filter(Intervention.student_id.in_(DEMO_STUDENT_IDS)).delete(synchronize_session=False)
    history_deleted = db.query(RiskHistory).filter(RiskHistory.student_id.in_(DEMO_STUDENT_IDS)).delete(synchronize_session=False)
    students_deleted = db.query(Student).filter(Student.id.in_(DEMO_STUDENT_IDS)).delete(synchronize_session=False)

    if any([timeline_deleted, interventions_deleted, history_deleted, students_deleted]):
        db.commit()
        logger.info(
            "🧹 Removed seeded demo data: students=%s, risk_history=%s, interventions=%s, timeline_events=%s",
            students_deleted,
            history_deleted,
            interventions_deleted,
            timeline_deleted,
        )


def run_seed(db: Session, include_demo_data: bool = False, purge_demo_data: bool = True):
    seed_users(db)

    if purge_demo_data:
        purge_demo_seed_data(db)

    if include_demo_data:
        seed_students(db)
        seed_interventions(db)

    logger.info("🌱 Database seeding complete")
