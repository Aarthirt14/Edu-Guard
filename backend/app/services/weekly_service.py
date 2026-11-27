"""Weekly records use IA marks out of 40; Student.marks is always a percentage."""
from app.services.prediction_service import refresh_prediction
from app.models.student import WeeklyRecord


def process_weekly_upload_for_student(db, student):
    db.flush()
    records = db.query(WeeklyRecord).filter(WeeklyRecord.student_id == student.id).order_by(WeeklyRecord.week_number).all()
    if records:
        student.attendance = records[-1].attendance_pct
        marks = [r.ia_marks for r in records if r.ia_marks is not None]
        if marks:
            student.marks = marks[-1] / 40 * 100
    return refresh_prediction(db, student)
