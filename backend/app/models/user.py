# ============================================================
# app/models/user.py — Users table
# ============================================================
from sqlalchemy import Column, String, Boolean, Enum
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    faculty = "faculty"
    counselor = "counselor"
    student = "student"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)          # e.g. "admin1"
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    assigned_class = Column(String, nullable=True)              # Faculty: "CS-A"
    is_active = Column(Boolean, default=True)

    # Relationships
    students = relationship("Student", back_populates="counselor_rel",
                            foreign_keys="Student.counselor_id", lazy="select")
