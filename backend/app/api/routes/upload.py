# ============================================================
# app/api/routes/upload.py — Dual upload endpoints
#   POST /api/upload/admission  → Admin uploads static CSV
#   POST /api/upload/weekly     → Faculty uploads 7-col weekly CSV
# ============================================================
import csv
import json
import io
import logging
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.models.student import Student, WeeklyRecord, RiskHistory
from app.models.user import User, UserRole
from app.services.auth_service import require_role
from app.ml.model import predict_early_risk, blend_scores
from app.services.weekly_service import process_weekly_upload_for_student

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload"])


# ─── Response schemas ───

class BulkUploadResult(BaseModel):
    created: int
    skipped: int
    errors: List[str]
    total: int


# ─── Helpers ───

def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "y")
    return False


def _parse_csv_rows(content: str) -> List[dict]:
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for row in reader:
        cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
        rows.append(cleaned)
    return rows


def _parse_json_rows(content: str) -> List[dict]:
    data = json.loads(content)
    if isinstance(data, dict):
        for key in ("students", "data", "records"):
            if key in data and isinstance(data[key], list):
                return data[key]
        raise ValueError("JSON object must contain a 'students', 'data', or 'records' array")
    if isinstance(data, list):
        return data
    raise ValueError("JSON must be an array or object with a data array")


def _read_file(file_bytes: bytes, filename: str) -> List[dict]:
    content = file_bytes.decode("utf-8-sig")
    if filename.endswith(".json"):
        return _parse_json_rows(content)
    return _parse_csv_rows(content)


def _safe_float(val, default=None):
    if val is None or (isinstance(val, str) and val.strip() in ("", "NULL", "null", "None")):
        return default
    return float(val)


def _safe_int(val, default=None):
    if val is None or (isinstance(val, str) and val.strip() in ("", "NULL", "null", "None")):
        return default
    return int(float(val))


# ═══════════════════════════════════════════════════════════════
# ENDPOINT 1 — Admin uploads admission data (Model 1)
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/admission",
    response_model=BulkUploadResult,
    summary="Admin: Upload admission (static) student data",
)
async def upload_admission_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    """
    Upload students_static.csv with admission-time data.
    Runs Model 1 (Early Risk) and stores baseline_risk_score.

    **CSV columns:** id, name, class_name, semester, Family_Income,
    Scholarship, Education_Loan, Father_Occupation, Mother_Occupation,
    Parent_Education, Home_Location, HighSchool_Grade, Admission_Quota
    """
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    raw = await file.read()
    try:
        rows = _read_file(raw, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="File contains no data.")

    created, skipped, errors = 0, 0, []

    for i, row in enumerate(rows):
        try:
            sid = str(row.get("id", "")).strip()
            name = str(row.get("name", "")).strip()
            class_name = str(row.get("class_name", "")).strip()
            semester = str(row.get("semester", "")).strip()

            if not sid or not name:
                errors.append(f"Row {i+1}: missing id or name")
                continue

            # Check duplicate
            existing = db.query(Student).filter(Student.id == sid).first()
            if existing:
                skipped += 1
                errors.append(f"Row {i+1} ({sid}): already exists — skipped")
                continue

            # Parse static fields
            family_income = _safe_float(row.get("Family_Income"), 30000)
            scholarship = str(row.get("Scholarship", "No")).strip()
            education_loan = str(row.get("Education_Loan", "No")).strip()
            father_occ = str(row.get("Father_Occupation", "Government Job")).strip()
            mother_occ = str(row.get("Mother_Occupation", "Homemaker")).strip()
            parent_edu = str(row.get("Parent_Education", "Graduate")).strip()
            home_location = str(row.get("Home_Location", "Semi-Urban")).strip()
            hs_grade = _safe_float(row.get("HighSchool_Grade"), 70)
            admission_quota = str(row.get("Admission_Quota", "Merit")).strip()

            # Run Model 1 — Early Risk
            baseline_score = predict_early_risk(
                family_income=family_income,
                scholarship=scholarship,
                education_loan=education_loan,
                father_occupation=father_occ,
                mother_occupation=mother_occ,
                parent_education=parent_edu,
                home_location=home_location,
                hs_grade=hs_grade,
                admission_quota=admission_quota,
            )

            student = Student(
                id=sid,
                name=name,
                class_name=class_name or "Unassigned",
                semester=semester or "Semester 1",
                family_income=family_income,
                scholarship=scholarship,
                education_loan=education_loan,
                father_occupation=father_occ,
                mother_occupation=mother_occ,
                parent_education=parent_edu,
                home_location=home_location,
                hs_grade=hs_grade,
                admission_quota=admission_quota,
                baseline_risk_score=baseline_score,
                risk_score=baseline_score,  # initially = baseline
                risk_trend="stable",
                has_financial_issue=(family_income < 20000 or education_loan == "Yes"),
            )
            db.add(student)
            db.add(RiskHistory(student_id=sid, risk_score=baseline_score))
            db.flush()
            created += 1

        except Exception as e:
            errors.append(f"Row {i+1} ({row.get('id', '?')}): {str(e)}")

    db.commit()
    logger.info(f"📤 Admission upload: {created} created, {skipped} skipped")

    return BulkUploadResult(
        created=created, skipped=skipped, errors=errors[:50], total=len(rows)
    )


# ═══════════════════════════════════════════════════════════════
# ENDPOINT 2 — Faculty uploads weekly data (Model 2)
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/weekly",
    response_model=BulkUploadResult,
    summary="Faculty: Upload weekly attendance/marks CSV",
)
async def upload_weekly_data(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.faculty, UserRole.admin)),
):
    """
    Upload 7-column weekly CSV. Backend stores records, computes
    engineered features (slope, averages, drops), runs Model 2,
    and updates the blended risk score.

    **CSV columns:** Student_ID, Week_Number, Attendance_Percentage,
    IA_Marks, Semester_Marks, Backlog_Count, Fee_Outstanding
    """
    filename = (file.filename or "").lower()
    if not filename.endswith((".csv", ".json")):
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    raw = await file.read()
    try:
        rows = _read_file(raw, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {e}")

    if not rows:
        raise HTTPException(status_code=400, detail="File contains no data.")

    created, skipped, errors = 0, 0, []
    affected_students = set()

    for i, row in enumerate(rows):
        try:
            sid = str(row.get("Student_ID", "")).strip()
            week = _safe_int(row.get("Week_Number"), None)
            att = _safe_float(row.get("Attendance_Percentage"), None)

            if not sid or week is None or att is None:
                errors.append(f"Row {i+1}: missing Student_ID / Week_Number / Attendance")
                continue

            # Verify student exists
            student = db.query(Student).filter(Student.id == sid).first()
            if not student:
                errors.append(f"Row {i+1} ({sid}): student not found — upload admission data first")
                continue

            # Check if this week already uploaded (update instead of duplicate)
            existing = (
                db.query(WeeklyRecord)
                .filter(WeeklyRecord.student_id == sid, WeeklyRecord.week_number == week)
                .first()
            )
            if existing:
                # Update existing record
                existing.attendance_pct = att
                existing.ia_marks = _safe_float(row.get("IA_Marks"))
                existing.semester_marks = _safe_float(row.get("Semester_Marks"))
                existing.backlog_count = _safe_int(row.get("Backlog_Count"))
                existing.fee_outstanding = _parse_bool(row.get("Fee_Outstanding", "No"))
                skipped += 1
            else:
                record = WeeklyRecord(
                    student_id=sid,
                    week_number=week,
                    attendance_pct=att,
                    ia_marks=_safe_float(row.get("IA_Marks")),
                    semester_marks=_safe_float(row.get("Semester_Marks")),
                    backlog_count=_safe_int(row.get("Backlog_Count")),
                    fee_outstanding=_parse_bool(row.get("Fee_Outstanding", "No")),
                )
                db.add(record)
                created += 1

            affected_students.add(sid)

        except Exception as e:
            errors.append(f"Row {i+1} ({row.get('Student_ID', '?')}): {str(e)}")

    db.flush()

    # Now run feature engineering + Model 2 for every affected student
    for sid in affected_students:
        try:
            student = db.query(Student).filter(Student.id == sid).first()
            if student:
                process_weekly_upload_for_student(db, student)
        except Exception as e:
            errors.append(f"Risk computation for {sid}: {str(e)}")

    db.commit()
    logger.info(f"📤 Weekly upload: {created} records, {len(affected_students)} students re-scored")

    return BulkUploadResult(
        created=created, skipped=skipped, errors=errors[:50], total=len(rows)
    )


# ═══════════════════════════════════════════════════════════════
# LEGACY — Keep old endpoint for backwards compat
# ═══════════════════════════════════════════════════════════════

@router.post(
    "/students",
    response_model=BulkUploadResult,
    summary="[Legacy] Bulk upload students",
    deprecated=True,
)
async def bulk_upload_students(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    """Legacy endpoint — redirects to admission upload."""
    return await upload_admission_data(file=file, db=db, _=_)
