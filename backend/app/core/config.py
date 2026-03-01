# ============================================================
# app/core/config.py — Centralised Settings
# ============================================================
from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # App
    APP_NAME: str = "EduGuard AI"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database
    DATABASE_URL: str = "sqlite:///./eduguard.db"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Google AI Studio (Gemini)
    GOOGLE_AI_STUDIO_API_KEY: str = ""
    GOOGLE_AI_MODEL: str = "gemini-1.5-flash"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500,http://localhost:5501,http://127.0.0.1:5501,http://localhost:3000"

    # Risk Thresholds
    HIGH_RISK_THRESHOLD: int = 70
    ATTENDANCE_ALERT_THRESHOLD: int = 60
    MARKS_DROP_ALERT_PERCENTAGE: int = 20

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = str(BACKEND_ENV_FILE)
        case_sensitive = True
        extra = "ignore"


settings = Settings()
