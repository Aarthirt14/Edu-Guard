from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.financial_support import (
    FinancialSupportCaseOut,
    StudentFinancialInput,
    AdminFinancialPlanInput,
)
from app.services.auth_service import get_current_user, require_role
from app.services.financial_support_service import (
    list_financial_cases,
    get_my_financial_case,
    submit_student_financial_input,
    update_admin_financial_plan,
)

router = APIRouter(prefix="/financial-support", tags=["Financial Support"])


@router.get("/cases", response_model=List[FinancialSupportCaseOut], summary="Admin: list financial support cases")
def admin_list_cases(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    rows = list_financial_cases(db)
    result: list[FinancialSupportCaseOut] = []
    for row in rows:
        out = FinancialSupportCaseOut.model_validate(row)
        out.student_name = row.student.name if row.student else None
        result.append(out)
    return result


@router.put("/cases/{case_id}/plan", response_model=FinancialSupportCaseOut, summary="Admin: publish support plan")
def admin_publish_plan(
    case_id: int,
    payload: AdminFinancialPlanInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    row = update_admin_financial_plan(db, case_id, payload)
    out = FinancialSupportCaseOut.model_validate(row)
    out.student_name = row.student.name if row.student else None
    return out


@router.get("/my-case", response_model=FinancialSupportCaseOut, summary="Student: get my financial support case")
def my_case(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = get_my_financial_case(db, current_user)
    out = FinancialSupportCaseOut.model_validate(row)
    out.student_name = row.student.name if row.student else None
    return out


@router.put("/my-case/input", response_model=FinancialSupportCaseOut, summary="Student: submit financial support details")
def my_case_input(
    payload: StudentFinancialInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = submit_student_financial_input(db, current_user, payload)
    out = FinancialSupportCaseOut.model_validate(row)
    out.student_name = row.student.name if row.student else None
    return out
