# ============================================================
# app/api/router.py — Master API router
# ============================================================
from fastapi import APIRouter
from app.api.routes import auth, students, interventions, analytics, reports, upload, settings, users, financial_support, counseling, copilot

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(interventions.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(upload.router)
api_router.include_router(settings.router)
api_router.include_router(users.router)
api_router.include_router(financial_support.router)
api_router.include_router(counseling.router)
api_router.include_router(copilot.router)
