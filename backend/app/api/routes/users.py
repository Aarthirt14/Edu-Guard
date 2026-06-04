from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.schemas.auth import UserOut
from app.schemas.user_management import (
    UserCreateRequest,
    FacultyClassUpdateRequest,
    StudentCommonPasswordRequest,
    StudentCommonPasswordResponse,
)
from app.services.auth_service import require_role
from app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=List[UserOut], summary="Admin: List faculty/counselor accounts")
def list_users(
    role: Optional[UserRole] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    query = db.query(User)

    if role:
        if role not in (UserRole.faculty, UserRole.counselor):
            raise HTTPException(status_code=400, detail="Only faculty/counselor roles are supported here")
        query = query.filter(User.role == role)
    else:
        query = query.filter(User.role.in_([UserRole.faculty, UserRole.counselor]))

    users = query.order_by(User.role.asc(), User.name.asc()).all()
    return [UserOut.model_validate(u) for u in users]


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Admin: Create faculty/counselor account")
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    if payload.role not in (UserRole.faculty, UserRole.counselor):
        raise HTTPException(status_code=400, detail="Only faculty or counselor accounts can be created from this page")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")

    user_id = (payload.id or "").strip()
    if not user_id:
        prefix = "faculty" if payload.role == UserRole.faculty else "counselor"
        count = db.query(User).filter(User.role == payload.role).count() + 1
        user_id = f"{prefix}{count}"

    if db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=400, detail="User ID already exists")

    assigned_class = (payload.assigned_class or "").strip() or None
    if payload.role == UserRole.faculty and not assigned_class:
        raise HTTPException(status_code=400, detail="assigned_class is required for faculty")

    new_user = User(
        id=user_id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        assigned_class=assigned_class if payload.role == UserRole.faculty else None,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserOut.model_validate(new_user)


@router.put("/{user_id}/class", response_model=UserOut, summary="Admin: Map faculty to class")
def update_faculty_class(
    user_id: str,
    payload: FacultyClassUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != UserRole.faculty:
        raise HTTPException(status_code=400, detail="Class assignment is only valid for faculty")

    assigned_class = (payload.assigned_class or "").strip()
    if not assigned_class:
        raise HTTPException(status_code=400, detail="assigned_class is required")

    user.assigned_class = assigned_class
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post(
    "/students/common-password",
    response_model=StudentCommonPasswordResponse,
    summary="Admin/Faculty: Set one common password for all students",
)
def set_students_common_password(
    payload: StudentCommonPasswordRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.faculty)),
):
    password = (payload.password or "").strip()
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    hashed = hash_password(password)
    students = db.query(Student).all()

    created = 0
    updated = 0
    linked = 0

    for student in students:
        student_user = None

        if student.user_id:
            student_user = db.query(User).filter(User.id == student.user_id).first()

        if not student_user:
            student_user = db.query(User).filter(User.id == student.id).first()

        if not student_user:
            base_email = f"{student.id.lower()}@students.eduguard.local"
            email_candidate = base_email
            suffix = 1
            while db.query(User).filter(User.email == email_candidate).first():
                email_candidate = f"{student.id.lower()}+{suffix}@students.eduguard.local"
                suffix += 1

            student_user = User(
                id=student.id,
                email=email_candidate,
                hashed_password=hashed,
                name=student.name,
                role=UserRole.student,
                is_active=True,
            )
            db.add(student_user)
            created += 1
        else:
            student_user.hashed_password = hashed
            student_user.role = UserRole.student
            student_user.is_active = True
            if not student_user.name:
                student_user.name = student.name
            updated += 1

        if student.user_id != student_user.id:
            student.user_id = student_user.id
            linked += 1

    db.commit()

    return StudentCommonPasswordResponse(
        total_students=len(students),
        accounts_created=created,
        accounts_updated=updated,
        links_updated=linked,
    )
