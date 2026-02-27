from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.financial_support import FinancialSupportCase
from app.models.intervention import Intervention, InterventionType
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.financial_support import StudentFinancialInput, AdminFinancialPlanInput


def _build_ai_recommendations(case: FinancialSupportCase) -> tuple[str, List[str]]:
    actions: List[str] = []

    amount = case.fee_outstanding_amount or 0
    if amount >= 50000:
        actions.append("Offer 4-6 month installment plan with reduced first installment.")
    elif amount >= 20000:
        actions.append("Offer 3-month installment plan and payment deadline counseling.")
    elif amount > 0:
        actions.append("Offer short-term installment with one follow-up in 14 days.")

    eligibility = (case.scholarship_eligibility or "").lower()
    category = (case.social_category or "").upper()
    income_band = (case.family_income_band or "").lower()

    if eligibility in ("yes", "likely", "unknown"):
        actions.append("Share scholarship checklist and document requirements immediately.")

    if category in ("BC", "MBC", "SC", "ST"):
        actions.append("Prioritize category-based government scholarship awareness and assisted application support.")

    if "below" in income_band or "low" in income_band:
        actions.append("Escalate to fee concession review committee for income-based support.")

    preferred = (case.preferred_support_type or "").lower()
    if "part" in preferred:
        actions.append("Share available on-campus part-time opportunities aligned with class timings.")
    if "install" in preferred and not any("installment" in a.lower() for a in actions):
        actions.append("Provide installment plan options and repayment calendar.")

    if not actions:
        actions = [
            "Schedule financial counseling call and collect missing documents.",
            "Share scholarship awareness resources and fee support options.",
        ]

    summary = "AI Support Summary: Student may need a blended finance plan with scholarship guidance and staged fee recovery."
    return summary, actions[:5]


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
    return (
        db.query(FinancialSupportCase)
        .order_by(FinancialSupportCase.updated_at.desc())
        .all()
    )


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
    summary, recommendations = _build_ai_recommendations(case)
    case.ai_summary = summary
    case.ai_recommendations = recommendations

    db.commit()
    db.refresh(case)
    return case


def update_admin_financial_plan(db: Session, case_id: int, payload: AdminFinancialPlanInput) -> FinancialSupportCase:
    case = db.query(FinancialSupportCase).filter(FinancialSupportCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Financial support case not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(case, key, value)

    if not payload.status:
        case.status = "Plan Shared"

    if not case.ai_recommendations:
        summary, recommendations = _build_ai_recommendations(case)
        case.ai_summary = summary
        case.ai_recommendations = recommendations

    db.commit()
    db.refresh(case)
    return case
