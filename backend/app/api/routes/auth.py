# ============================================================
# app/api/routes/auth.py
# POST /api/auth/login  →  JWT token
# GET  /api/auth/me     →  current user
# ============================================================
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.services.auth_service import authenticate_user, get_current_user
from app.core.security import create_access_token
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, summary="Login and get JWT token")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate with email, password, and role.
    Returns a JWT token to use in all subsequent requests.

    **Frontend usage (auth.js `handleLogin`):**
    ```js
    const res = await fetch('http://localhost:8000/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, role: selectedRole })
    });
    const data = await res.json();
    localStorage.setItem('eduguard_token', data.access_token);
    localStorage.setItem('eduguard_user', JSON.stringify(data.user));
    ```
    """
    user = authenticate_user(db, payload.email, payload.password, payload.role)
    token = create_access_token({"sub": user.id, "role": user.role.value})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="Get current logged-in user")
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post("/logout", summary="Logout (client should discard token)")
def logout():
    """
    JWT is stateless — logout just signals the frontend to clear localStorage.
    For production, implement a token denylist with Redis.
    """
    return {"message": "Logged out. Please clear your token on the client."}
