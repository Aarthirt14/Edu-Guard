# ============================================================
# app/services/weekly_service.py — Feature engineering from
#   raw weekly records → dynamic model input
# ============================================================
import numpy as np
import logging
from sqlalchemy.orm import Session
from app.models.student import Student, WeeklyRecord, RiskHistory
from app.ml.model import predict_dynamic_risk, blend_scores

logger = logging.getLogger(__name__)


def compute_engineered_features(records: list[WeeklyRecord], student: Student) -> dict:
    """
    Takes all weekly records for a student and computes the 14 engineered
    features required by Model 2 (Dynamic Risk).

    Returns a dict ready to pass to predict_dynamic_risk().
    """
    # Sort by week number
    records = sorted(records, key=lambda r: r.week_number)

    weeks_tracked = len(records)
    if weeks_tracked == 0:
        return None

    # ── Attendance features ──
    attendances = [r.attendance_pct for r in records]
    att_current = attendances[-1]

    # att_avg_4w — mean of last 4 weeks
    last_4 = attendances[-4:] if len(attendances) >= 4 else attendances
    att_avg_4w = float(np.mean(last_4))

    # att_total_drop — first week minus current
    att_total_drop = attendances[0] - att_current

    # att_slope — linear regression slope across all weeks
    if len(attendances) >= 2:
        week_nums = np.arange(1, len(attendances) + 1, dtype=float)
        att_slope = float(np.polyfit(week_nums, attendances, 1)[0])
    else:
        att_slope = 0.0

    # ── IA Marks features ──
    ia_values = [r.ia_marks for r in records if r.ia_marks is not None]
    has_ia_data = 1 if len(ia_values) > 0 else 0
    ia_latest = ia_values[-1] if ia_values else 0.0
    ia_avg = float(np.mean(ia_values)) if ia_values else 0.0

    # ── Backlog features ──
    backlog_values = [(r.week_number, r.backlog_count or 0) for r in records]
    backlog_current = backlog_values[-1][1]
    if len(backlog_values) >= 2:
        backlog_growing = 1 if backlog_values[-1][1] > backlog_values[-2][1] else 0
    else:
        backlog_growing = 0

    # ── Fee outstanding ──
    fee_outstanding = 1 if records[-1].fee_outstanding else 0

    # ── Static fields from student (for merging) ──
    family_income = student.family_income or 30000
    hs_grade = student.hs_grade or 70
    home_location = student.home_location or "Semi-Urban"

    return {
        "att_current": att_current,
        "att_avg_4w": att_avg_4w,
        "att_total_drop": att_total_drop,
        "att_slope": att_slope,
        "ia_latest": ia_latest,
        "ia_avg": ia_avg,
        "has_ia_data": has_ia_data,
        "backlog_current": backlog_current,
        "backlog_growing": backlog_growing,
        "fee_outstanding": fee_outstanding,
        "weeks_tracked": weeks_tracked,
        "family_income": family_income,
        "hs_grade": hs_grade,
        "home_location": home_location,
    }


def process_weekly_upload_for_student(db: Session, student: Student):
    """
    After new weekly records are inserted for a student:
    1. Fetch all weekly records
    2. Compute engineered features (slopes, averages, drops, trends)
    3. Run Model 2 (Dynamic Risk)
    4. Blend with Model 1 (baseline_risk_score)
    5. Update student risk_score, dynamic_risk_score, weeks_tracked
    """
    records = (
        db.query(WeeklyRecord)
        .filter(WeeklyRecord.student_id == student.id)
        .order_by(WeeklyRecord.week_number.asc())
        .all()
    )

    if not records:
        return

    features = compute_engineered_features(records, student)
    if not features:
        return

    # Run dynamic model
    dynamic_score = predict_dynamic_risk(**features)

    # Get baseline score (Model 1) — if not set, use a default
    baseline = student.baseline_risk_score if student.baseline_risk_score is not None else 50.0

    # Blend
    weeks = features["weeks_tracked"]
    blended = blend_scores(baseline, dynamic_score, weeks)

    # Update student
    old_score = student.risk_score or 0
    student.dynamic_risk_score = dynamic_score
    student.risk_score = blended
    student.weeks_tracked = weeks
    student.risk_trend = "up" if blended > old_score else ("down" if blended < old_score else "stable")

    # Also update attendance/marks for display (latest values)
    student.attendance = features["att_current"]
    if features["has_ia_data"]:
        student.marks = features["ia_latest"]

    # Record risk history
    db.add(RiskHistory(student_id=student.id, risk_score=blended))

    logger.info(f"📊 {student.id}: baseline={baseline}, dynamic={dynamic_score}, "
                f"blended={blended} (weeks={weeks})")
