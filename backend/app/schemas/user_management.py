from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class UserCreateRequest(BaseModel):
    id: str | None = None
    email: EmailStr
    password: str
    name: str
    role: UserRole
    assigned_class: str | None = None


class FacultyClassUpdateRequest(BaseModel):
    assigned_class: str
