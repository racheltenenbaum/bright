import os

# Must be set before any app imports so module-level reads pick them up
os.environ["SECRET_KEY"] = "test-secret-key-bright"
os.environ["DATABASE_URL"] = "sqlite:///./test_bright.db"
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-google-key")
os.environ.setdefault("ASTRONOMY_API_KEY", "test-astro-key")
# Low limits so rate-limit tests only need 3+1 requests
os.environ["RATE_LIMIT_LOGIN"] = "3/minute"
os.environ["RATE_LIMIT_WEATHER"] = "3/minute"
os.environ["RATE_LIMIT_SHADOW"] = "3/minute"

import pytest
import bcrypt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, User
from src.database import get_db
from src.main import app
from src.auth import create_access_token

SQLITE_URL = "sqlite:///./test_bright.db"
engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clean_tables():
    # Reset rate limiter storage before each test so limits don't bleed across tests
    from src.limiter import limiter
    storage = limiter._storage
    for attr in ("storage", "_events", "_data"):
        if hasattr(storage, attr):
            getattr(storage, attr).clear()
            break
    yield
    db = TestingSessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user(db):
    hashed = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    user = User(first_name="Test", email="test@example.com", hashed_password=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}
