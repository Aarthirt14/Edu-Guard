"""Validated CSV/JSON imports with row savepoints and authoritative scoring."""
import csv
import io
import json
import math
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.db.database import get_db
from app.models.student import Student, WeeklyRecord
from app.models.user import UserRole
from app.schemas.student import StudentCreate
from app.services.auth_service import require_role
from app.services.access import ensure_student_access
from app.services.prediction_service import refresh_prediction, EARLY_FIELDS
from app.services.weekly_service import process_weekly_upload_for_student

router = APIRouter(prefix="/upload", tags=["Upload"])


class BulkUploadResult(BaseModel):
    created: int
    skipped: int
    updated: int = 0
    errors: list[str]
    total: int


def number(value, low, high, optional=False, integer=False):
    if value in (None, "", "NULL", "null") and optional:
        return None
    val = float(value)
    if not math.isfinite(val) or not low <= val <= high or (integer and not val.is_integer()):
        raise ValueError(f"Expected {'integer' if integer else 'number'} between {low} and {high}")
    return int(val) if integer else val


def boolean(value):
    value = str(value).strip().lower()
    if value not in ("yes", "no", "true", "false", "1", "0"):
        raise ValueError("Fee_Outstanding must be Yes or No")
    return value in ("yes", "true", "1")


async def read_rows(file):
    if not (file.filename or "").lower().endswith((".csv", ".json")):
        raise HTTPException(400, "Upload CSV or JSON")
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Upload limit is 5 MB")
    try:
        content = raw.decode("utf-8-sig")
        if file.filename.lower().endswith(".json"):
            rows = json.loads(content)
            if isinstance(rows, dict):
                rows = next((rows[k] for k in ("students", "data", "records") if k in rows), None)
        else:
            rows = [{k.strip(): v.strip() if isinstance(v, str) else v for k, v in r.items() if k} for r in csv.DictReader(io.StringIO(content))]
        if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
            raise ValueError("Expected a nonempty array of records")
        return rows
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(400, f"Invalid file: {exc}")


@router.post("/admission", response_model=BulkUploadResult)
async def upload_admission_data(file: UploadFile = File(...), db=Depends(get_db), _=Depends(require_role(UserRole.admin))):
    rows = await read_rows(file)
    ensure_outer_transaction(db)
    created = skipped = 0
    errors = []
    for i, row in enumerate(rows, 1):
        try:
            with db.begin_nested():
                sid = str(row.get("id", "")).strip()
                if not sid or not str(row.get("name", "")).strip() or not row.get("class_name") or not row.get("semester"):
                    raise ValueError("id, name, class_name and semester are required")
                if db.get(Student, sid):
                    skipped += 1
                    continue
                profile = {attr: row.get(key) or None for key, attr in EARLY_FIELDS.items()}
                # Missing fields remain missing; no invented family background.
                profile["admission_quota"] = row.get("Admission_Quota") or None
                data = StudentCreate(id=sid, name=row["name"], class_name=row["class_name"], semester=row["semester"], attendance=100, marks=100, **profile)
                student = Student(**data.model_dump(), risk_trend="stable")
                db.add(student)
                db.flush()
                refresh_prediction(db, student)
            created += 1
        except (ValueError, TypeError) as exc:
            errors.append(f"Row {i}: {exc}")
    db.commit()
    return BulkUploadResult(created=created, skipped=skipped, errors=errors[:50], total=len(rows))


@router.post("/weekly", response_model=BulkUploadResult)
async def upload_weekly_data(file: UploadFile = File(...), db=Depends(get_db), user=Depends(require_role(UserRole.faculty, UserRole.admin))):
    """IA_Marks is out of IA_Max (default 40), stored canonically out of 40.

    Week_Number is an absolute week index across the student's tracked enrolment.
    Blank IA is allowed; missing backlog/fee information is rejected.
    """
    rows = await read_rows(file)
    ensure_outer_transaction(db)
    created = updated = 0
    errors = []
    affected = set()
    for i, row in enumerate(rows, 1):
        try:
            sid = str(row.get("Student_ID", "")).strip()
            ensure_student_access(db, user, sid)
            week = number(row.get("Week_Number"), 1, 520, integer=True)
            ia_max = number(row.get("IA_Max", 40), .01, 10000)
            ia = number(row.get("IA_Marks"), 0, ia_max, optional=True)
            values = dict(attendance_pct=number(row.get("Attendance_Percentage"), 0, 100),
                ia_marks=None if ia is None else ia / ia_max * 40,
                semester_marks=number(row.get("Semester_Marks"), 0, 100, optional=True),
                backlog_count=number(row.get("Backlog_Count"), 0, 100, integer=True),
                fee_outstanding=boolean(row.get("Fee_Outstanding")))
            with db.begin_nested():
                record = db.query(WeeklyRecord).filter_by(student_id=sid, week_number=week).first()
                if record:
                    for k, v in values.items():
                        setattr(record, k, v)
                    updated += 1
                else:
                    db.add(WeeklyRecord(student_id=sid, week_number=week, **values))
                    created += 1
                affected.add(sid)
        except (ValueError, TypeError, HTTPException) as exc:
            errors.append(f"Row {i}: {getattr(exc, 'detail', str(exc))}")
    try:
        db.flush()
        for sid in affected:
            process_weekly_upload_for_student(db, db.get(Student, sid))
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(503, "Prediction unavailable; upload rolled back. Retry after checking model health.")
    return BulkUploadResult(created=created, updated=updated, skipped=0, errors=errors[:50], total=len(rows))


@router.post("/students", response_model=BulkUploadResult, deprecated=True)
async def bulk_upload_students(file: UploadFile = File(...), db=Depends(get_db), _=Depends(require_role(UserRole.admin))):
    return await upload_admission_data(file, db, _)


def ensure_outer_transaction(db):
    # sqlite legacy transaction control does not BEGIN on SELECT or SAVEPOINT.
    # Explicit BEGIN prevents a released savepoint from committing the upload.
    connection = db.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")
