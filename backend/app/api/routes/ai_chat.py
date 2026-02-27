"""
app/api/routes/ai_chat.py — AI Assistant chat endpoint
POST /api/ai/chat   → sends message, returns AI response
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.dependencies import get_db, get_current_user
from app.services.ai_service import chat

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse, summary="Send message to EduGuard AI Assistant")
def ai_chat(
    req: ChatRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Send any question about high-risk students or interventions.
    The AI has access to live student data from the database.
    """
    reply = chat(req.message, db)
    return ChatResponse(response=reply)
