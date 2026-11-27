"""Persisted student requests and staff replies; no external message delivery."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.models.student import Student
from app.models.user import UserRole, User
from app.models.support_request import SupportRequest, SupportReply
from app.services.auth_service import get_current_user, require_role

router = APIRouter(prefix='/support', tags=['Support inbox'])


class NewRequest(BaseModel):
    category: Literal['Academic', 'Counseling', 'Financial', 'Attendance']
    message: str = Field(min_length=1, max_length=4000)
    submission_key: UUID

    @field_validator('message')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Message cannot be blank')
        return value.strip()


class NewReply(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    status: Literal['Open', 'In Progress', 'Resolved'] | None = None
    owner_id: str | None = None
    _nonblank = field_validator('message')(NewRequest.nonblank.__func__)


def linked_student(db, user):
    student = db.query(Student).filter_by(user_id=user.id).first()
    if not student:
        raise HTTPException(404, 'No linked student profile')
    return student


def authorised_request(db, user, ident):
    request = db.get(SupportRequest, ident)
    if not request:
        raise HTTPException(404, 'Request not found')
    if user.role == UserRole.student:
        if request.student_id != linked_student(db, user).id:
            raise HTTPException(403, 'Access denied')
    elif user.role not in (UserRole.admin, UserRole.counselor):
        raise HTTPException(403, 'Only the student or support staff can read this conversation')
    return request


def serialise(row):
    return {'id': row.id, 'student_id': row.student_id, 'category': row.category,
        'message': row.message, 'status': row.status, 'owner_id': row.owner_id,
        'created_at': row.created_at, 'replies': [
            {'id': reply.id, 'author_name': reply.author_name, 'author_role': reply.author_role,
             'message': reply.message, 'created_at': reply.created_at} for reply in row.replies]}


@router.get('/requests')
def list_requests(db=Depends(get_db), user=Depends(get_current_user)):
    query = db.query(SupportRequest).options(selectinload(SupportRequest.replies))
    if user.role == UserRole.student:
        query = query.filter_by(student_id=linked_student(db, user).id)
    elif user.role not in (UserRole.admin, UserRole.counselor):
        raise HTTPException(403, 'Support inbox is restricted to students and support staff')
    return [serialise(r) for r in query.order_by(SupportRequest.created_at.desc()).limit(200)]


@router.post('/requests', status_code=201)
def create_request(data: NewRequest, db=Depends(get_db), user=Depends(require_role(UserRole.student))):
    student = linked_student(db, user)
    existing = db.query(SupportRequest).filter_by(student_id=student.id, submission_key=str(data.submission_key)).first()
    if existing:
        return serialise(existing)
    row = SupportRequest(student_id=student.id, submission_key=str(data.submission_key), category=data.category, message=data.message)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialise(row)


@router.get('/requests/{ident}')
def get_request(ident: int, db=Depends(get_db), user=Depends(get_current_user)):
    return serialise(authorised_request(db, user, ident))


@router.post('/requests/{ident}/replies')
def reply_to_request(ident: int, data: NewReply, db=Depends(get_db), user=Depends(get_current_user)):
    row = authorised_request(db, user, ident)
    if user.role == UserRole.student:
        if data.status is not None or data.owner_id is not None:
            raise HTTPException(403, 'Only staff can assign requests or set status')
        row.status = 'Open'
    else:
        owner_id = data.owner_id or row.owner_id or user.id
        owner = db.get(User, owner_id)
        if not owner or not owner.is_active or owner.role not in (UserRole.admin, UserRole.counselor):
            raise HTTPException(422, 'Owner must be active support staff')
        row.owner_id = owner_id
        row.status = data.status or 'In Progress'
    db.add(SupportReply(request_id=row.id, author_id=user.id, author_name=user.name,
        author_role=user.role.value, message=data.message))
    db.commit()
    db.refresh(row)
    return serialise(row)
