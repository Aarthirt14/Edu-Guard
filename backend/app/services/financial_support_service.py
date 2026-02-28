from typing import List, Optional
import importlib
import json
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.financial_support import FinancialSupportCase
from app.models.intervention import Intervention, InterventionType
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.financial_support import StudentFinancialInput, AdminFinancialPlanInput
from app.services.student_service import get_risk_trend_factors


Anthropic = None
try:
    anthropic_mod = importlib.import_module("anthropic")
    Anthropic = getattr(anthropic_mod, "Anthropic", None)
except Exception:
    Anthropic = None


LEGACY_AI_LINES = {
    "Schedule financial counseling call and collect missing documents.",
    "Share scholarship awareness resources and fee support options.",
}


def _extract_json(raw_text: str) -> Optional[dict]:
    text = (raw_text or "").strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    left = text.find("{")
    right = text.rfind("}")
    if left != -1 and right > left:
        try:
            return json.loads(text[left:right + 1])
        except Exception:
            return None
    return None


def _dedupe_keep_order(lines: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = (line or "").strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _heuristic_financial_ai(case: FinancialSupportCase, db: Optional[Session] = None) -> tuple[str, List[str]]:
    actions: List[str] = []
    summary_signals: List[str] = []

    student = case.student
    amount = float(case.fee_outstanding_amount or 0)
    eligibility = (case.scholarship_eligibility or "").strip().lower()
    category = (case.social_category or "").strip().upper()
    income_band = (case.family_income_band or "").strip().lower()
    preferred = (case.preferred_support_type or "").strip().lower()
    applied = (case.scholarship_applied or "").strip().lower()
    notes = (case.student_notes or "").strip().lower()

    if amount >= 50000:
        summary_signals.append(f"high outstanding fee (₹{int(amount):,})")
        actions.append("Design a 4–6 month staged installment with reduced first payment and weekly reminder checkpoints.")
    elif amount >= 20000:
        summary_signals.append(f"moderate fee burden (₹{int(amount):,})")
        actions.append("Offer a 3-month installment plan and confirm first payment deadline with the student.")
    elif amount > 0:
        summary_signals.append(f"fee due (₹{int(amount):,})")
        actions.append("Offer a short-term installment option with one follow-up after 14 days.")
    else:
        actions.append("Validate current fee statement with accounts office and collect exact pending amount before finalizing plan.")

    if eligibility in ("yes", "likely", "unknown"):
        summary_signals.append("scholarship path available")
        actions.append("Start scholarship workflow immediately: document checklist, submission timeline, and application tracking owner.")

    if applied in ("no", "not applied", "false"):
        actions.append("Schedule a 20-minute assisted application session so scholarship filing is completed this week.")

    if category in ("BC", "MBC", "SC", "ST"):
        summary_signals.append(f"category support opportunity ({category})")
        actions.append("Map eligible category-based schemes and provide assisted enrollment support with required proof documents.")

    if "below" in income_band or "low" in income_band:
        summary_signals.append("income-sensitive case")
        actions.append("Escalate to fee concession committee with income-band evidence for partial waiver review.")

    if "install" in preferred:
        actions.append("Share two installment variants (conservative/aggressive) and confirm preferred repayment calendar.")
    if "scholar" in preferred:
        actions.append("Prioritize scholarship-first strategy and bridge with temporary installment until approval.")
    if "part" in preferred:
        actions.append("Share on-campus part-time options aligned with class timetable and expected monthly earning range.")

    if "medical" in notes or "health" in notes:
        summary_signals.append("health-related financial strain")
        actions.append("Collect medical hardship proof and route to emergency student welfare fund review.")
    if "job" in notes or "lost" in notes or "income" in notes:
        summary_signals.append("household income instability")
        actions.append("Prioritize immediate interim relief while long-cycle scholarship/waiver decision is pending.")

    if student is not None:
        risk_score = float(student.risk_score or 0)
        attendance = float(student.attendance or 0)
        marks = float(student.marks or 0)

        if risk_score >= 85:
            summary_signals.append(f"critical dropout risk ({risk_score:.1f})")
            actions.append("Mark case as urgent and align counselor + accounts follow-up within 48 hours.")
        elif risk_score >= 75:
            summary_signals.append(f"high dropout risk ({risk_score:.1f})")
            actions.append("Set a weekly financial-risk review cadence until risk drops below 70.")

        if attendance < 65:
            actions.append("Link financial plan milestones with attendance recovery check-ins to reduce immediate dropout risk.")
        if marks < 45:
            actions.append("Coordinate with academic support mentor while financial plan is active to stabilize performance.")

        if db is not None:
            try:
                trend = get_risk_trend_factors(db, student.id)
            except Exception:
                trend = None

            if trend:
                attendance_trend = str(trend.get("attendance_trend") or "").lower()
                marks_trend = str(trend.get("marks_trend") or "").lower()
                fee_trend = str(trend.get("fee_trend") or "").lower()
                drivers = [str(d).strip() for d in (trend.get("drivers") or []) if str(d).strip()]

                if attendance_trend == "declining":
                    summary_signals.append("attendance declining")
                    actions.append("Tie installment due dates with attendance check-ins and trigger mentor follow-up on missed classes.")

                if marks_trend == "declining":
                    summary_signals.append("marks declining")
                    actions.append("Bundle financial support with academic remediation so financial stress does not compound grade decline.")

                if fee_trend == "declining":
                    summary_signals.append("fee pressure increasing")
                    actions.append("Escalate to accounts for interim hold on penalties while plan approval is processed.")

                if drivers:
                    actions.append(f"Discuss trend drivers with student: {drivers[0]}")

    actions = _dedupe_keep_order(actions)
    if not actions:
        actions = [
            "Schedule a case review call and gather missing financial documents.",
            "Prepare a blended support path (scholarship + installment) with clear timeline and owner.",
        ]

    if summary_signals:
        summary = "AI Financial Insight: " + "; ".join(summary_signals[:3]).capitalize() + "."
    else:
        summary = "AI Financial Insight: Requires blended fee support planning based on pending data and affordability constraints."

    return summary, actions[:5]


def _llm_financial_ai(
    case: FinancialSupportCase,
    fallback_summary: str,
    fallback_actions: List[str],
    db: Optional[Session] = None,
) -> Optional[tuple[str, List[str]]]:
    if not settings.ANTHROPIC_API_KEY or Anthropic is None:
        return None

    student = case.student
    context = {
        "student_id": case.student_id,
        "student_name": student.name if student else None,
        "class_name": student.class_name if student else None,
        "risk_score": float(student.risk_score or 0) if student else None,
        "attendance": float(student.attendance or 0) if student else None,
        "marks": float(student.marks or 0) if student else None,
        "fee_outstanding_amount": case.fee_outstanding_amount,
        "scholarship_eligibility": case.scholarship_eligibility,
        "social_category": case.social_category,
        "family_income_band": case.family_income_band,
        "scholarship_applied": case.scholarship_applied,
        "preferred_support_type": case.preferred_support_type,
        "student_notes": case.student_notes,
    }

    if db is not None and student is not None:
        try:
            trend = get_risk_trend_factors(db, student.id)
            context["trend"] = {
                "attendance_trend": trend.get("attendance_trend"),
                "marks_trend": trend.get("marks_trend"),
                "fee_trend": trend.get("fee_trend"),
                "drivers": trend.get("drivers") or [],
            }
        except Exception:
            pass

    prompt = (
        "You are an education financial aid co-pilot. "
        "Return strict JSON only with keys: summary (string), actions (array of 3-5 short actionable strings). "
        "Avoid generic wording and tailor to provided case context.\n\n"
        f"Case context: {json.dumps(context, ensure_ascii=False)}\n"
        f"Fallback summary: {fallback_summary}\n"
        f"Fallback actions: {json.dumps(fallback_actions, ensure_ascii=False)}\n"
    )

    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=320,
            temperature=0.2,
            system="Be precise, student-safe, and produce valid JSON only.",
            messages=[{"role": "user", "content": prompt}],
        )

        text_out = ""
        content = getattr(response, "content", None)
        if isinstance(content, list) and content:
            first = content[0]
            text_out = getattr(first, "text", "") if first is not None else ""

        parsed = _extract_json(text_out)
        if not parsed:
            return None

        summary = str(parsed.get("summary") or "").strip()
        raw_actions = parsed.get("actions") or []
        actions = _dedupe_keep_order([str(a).strip() for a in raw_actions if str(a).strip()])[:5]

        if not summary or len(actions) < 2:
            return None
        return summary, actions
    except Exception:
        return None


def _needs_ai_refresh(case: FinancialSupportCase) -> bool:
    if not case.ai_recommendations:
        return True

    recs = [str(r).strip() for r in (case.ai_recommendations or []) if str(r).strip()]
    if not recs:
        return True
    if len(recs) < 2:
        return True

    if any(r in LEGACY_AI_LINES for r in recs):
        return True

    summary = (case.ai_summary or "").strip().lower()
    if summary.startswith("ai support summary: student may need a blended finance plan"):
        return True

    return False


def _build_ai_recommendations(case: FinancialSupportCase, db: Optional[Session] = None) -> tuple[str, List[str]]:
    heuristic_summary, heuristic_actions = _heuristic_financial_ai(case, db=db)
    llm_out = _llm_financial_ai(case, heuristic_summary, heuristic_actions, db=db)
    if llm_out:
        return llm_out
    return heuristic_summary, heuristic_actions


def ensure_financial_case_for_intervention(db: Session, intervention: Intervention) -> FinancialSupportCase | None:
    if intervention.type != InterventionType.financial_support:
        return None

    existing = db.query(FinancialSupportCase).filter(FinancialSupportCase.intervention_id == intervention.id).first()
    if existing:
        return existing

    case = FinancialSupportCase(
        intervention_id=intervention.id,
        student_id=intervention.student_id,
        status="Awaiting Student Input",
    )
    db.add(case)
    db.flush()
    return case


def list_financial_cases(db: Session) -> list[FinancialSupportCase]:
    rows = (
        db.query(FinancialSupportCase)
        .options(joinedload(FinancialSupportCase.student))
        .order_by(FinancialSupportCase.updated_at.desc())
        .all()
    )

    changed = False
    for case in rows:
        if _needs_ai_refresh(case):
            summary, recommendations = _build_ai_recommendations(case, db=db)
            case.ai_summary = summary
            case.ai_recommendations = recommendations
            changed = True

    if changed:
        db.commit()

    return rows


def _resolve_student_for_user(db: Session, current_user: User) -> Student:
    if current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="Only students can access this endpoint")

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        student = db.query(Student).filter(Student.email == current_user.email).first()
    if not student and current_user.id.startswith("STU-"):
        student = db.query(Student).filter(Student.id == current_user.id).first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="No linked student profile found. Please contact admin to map your account.",
        )
    return student


def get_my_financial_case(db: Session, current_user: User) -> FinancialSupportCase:
    student = _resolve_student_for_user(db, current_user)

    case = (
        db.query(FinancialSupportCase)
        .options(joinedload(FinancialSupportCase.student))
        .filter(FinancialSupportCase.student_id == student.id)
        .order_by(FinancialSupportCase.updated_at.desc())
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="No financial support case assigned yet")
    return case


def submit_student_financial_input(db: Session, current_user: User, payload: StudentFinancialInput) -> FinancialSupportCase:
    case = get_my_financial_case(db, current_user)

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(case, key, value)

    case.status = "Student Input Submitted"
    summary, recommendations = _build_ai_recommendations(case, db=db)
    case.ai_summary = summary
    case.ai_recommendations = recommendations

    db.commit()
    db.refresh(case)
    return case


def update_admin_financial_plan(db: Session, case_id: int, payload: AdminFinancialPlanInput) -> FinancialSupportCase:
    case = (
        db.query(FinancialSupportCase)
        .options(joinedload(FinancialSupportCase.student))
        .filter(FinancialSupportCase.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Financial support case not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(case, key, value)

    if not payload.status:
        case.status = "Plan Shared"

    if not case.ai_recommendations:
        summary, recommendations = _build_ai_recommendations(case, db=db)
        case.ai_summary = summary
        case.ai_recommendations = recommendations

    db.commit()
    db.refresh(case)
    return case
