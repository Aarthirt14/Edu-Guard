# ============================================================
# app/schemas/auth.py — Auth request/response schemas
# ============================================================
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: str
    password: str
    role: UserRole

    model_config = {"json_schema_extra": {
        "example": {
            "email": "admin@eduguard.com",
            "password": "admin123",
            "role": "admin"
        }
    }}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    assigned_class: str | None = None

    model_config = {"from_attributes": True}


TokenResponse.model_rebuild()
