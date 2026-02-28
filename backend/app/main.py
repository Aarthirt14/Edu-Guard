# ============================================================
# app/main.py — FastAPI Application Entry Point
# EduGuard AI — Student Dropout Prevention System
# ============================================================
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.database import engine, Base, SessionLocal
from app.api.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables, seed data, warm up ML models."""
    logger.info("🚀 EduGuard AI Backend starting up...")

    # Create all DB tables
    import app.models.user
    import app.models.student
    import app.models.intervention
    import app.models.settings
    import app.models.financial_support
    import app.models.counseling_session
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables ready")

    # Seed initial data
    db = SessionLocal()
    try:
        from app.db.seed import run_seed
        run_seed(db, include_demo_data=False, purge_demo_data=True)
    finally:
        db.close()

    # Warm up both ML models (trains & saves if not found)
    from app.ml.model import load_model
    load_model()

    yield

    logger.info("🛑 EduGuard AI Backend shutting down")


app = FastAPI(
    title="EduGuard AI — Backend API",
    description="""
## 🛡️ EduGuard AI Backend

REST API powering the EduGuard student dropout prediction dashboard.

### Dual ML Model Architecture
- **Model 1 (Early Risk)**: RandomForest trained on static admission data (10,000 rows)
  - Runs once at admission — `baseline_risk_score` stored permanently
- **Model 2 (Dynamic Risk)**: GradientBoosting trained on weekly engineered features (10,000 rows)
  - Re-runs every week using attendance slope, IA trends, backlog growth

### Blended Score Formula
| Weeks Tracked | Early Weight | Dynamic Weight |
|---------------|-------------|----------------|
| 1–2 | 60% | 40% |
| 3–7 | 40% | 60% |
| 8+  | 20% | 80% |

### Key Endpoints
- `POST /api/auth/login` — Authenticate and get JWT
- `GET /api/students/high-risk` — All high-risk students (role-filtered)
- `POST /api/students/predict` — ML dropout risk prediction
- `POST /api/interventions/` — Assign intervention
- `GET /api/analytics/dashboard` — Dashboard stat cards
- `POST /api/analytics/ai-chat` — AI assistant

### Default Credentials (seeded)
| Role | Email | Password |
|------|-------|----------|
| Admin | admin@eduguard.com | admin123 |
| Faculty | faculty@eduguard.com | faculty123 |
| Counselor | counselor@eduguard.com | counselor123 |
| Student | student@eduguard.com | student123 |
    """,
    version="2.0.0",
    lifespan=lifespan,
)

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again."}
    )


app.include_router(api_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "service": "EduGuard AI Backend",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "models": {
            "model1": "RandomForest (Early Risk) — 82% accuracy, AUC 0.90",
            "model2": "GradientBoosting (Dynamic Risk) — 95% accuracy, AUC 0.99",
        }
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
