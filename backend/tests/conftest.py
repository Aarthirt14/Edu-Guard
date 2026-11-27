import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import Base, get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.core.security import create_access_token

@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for role, cls in [("admin", None), ("counselor", None), ("faculty", "A"), ("student", None)]:
        session.add(User(id=role, email=f"{role}@example.com", name=role, role=UserRole(role), hashed_password="unused", is_active=True, assigned_class=cls))
    session.add_all([Student(id="A1", name="One", class_name="A", semester="Semester 1", user_id="student", attendance=80, marks=70), Student(id="B1", name="Two", class_name="B", semester="Semester 1", attendance=60, marks=50)])
    session.commit()
    yield session
    session.close()
    engine.dispose()

@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def headers():
    return lambda role: {"Authorization": "Bearer " + create_access_token({"sub": role, "role": role})}
