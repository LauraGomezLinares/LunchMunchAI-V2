"""Shared test configuration and reusable fixtures for unit and integration testing.

Architecture notes:
- Uses an in-memory SQLite database ('sqlite://') with SQLAlchemy StaticPool to ensure
  all FastAPI TestClient threads and background queries share the exact same connection.
- Overrides database sessions and mocks external identity providers (Firebase Admin SDK)
  at the service boundary to guarantee isolated, reproducible test runs.
"""

from collections.abc import Generator
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.services import auth_service

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    """Provide an isolated, clean in-memory database session per test."""
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="mock_firebase")
def mock_firebase_fixture(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, Any] | None], dict[str, Any]]:
    """Mock Firebase ID token verification at the service and security boundaries."""
    default_claims: dict[str, Any] = {
        "uid": "test-firebase-uid-123",
        "email": "tester@mealmuse.com",
        "name": "MealMuse Tester",
    }

    def _set_claims(custom_claims: dict[str, Any] | None = None) -> dict[str, Any]:
        claims = default_claims.copy()
        if custom_claims:
            claims.update(custom_claims)
        monkeypatch.setattr(auth_service, "verify_firebase_token", lambda _: claims)
        return claims

    _set_claims()
    return _set_claims


@pytest.fixture(name="test_user")
def test_user_fixture(db_session: Session) -> User:
    """Create and return a pre-seeded test user in the isolated database."""
    user = User(
        firebase_uid="test-firebase-uid-123",
        email="tester@mealmuse.com",
        nombre="MealMuse Tester",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(test_user: User) -> dict[str, str]:
    """Generate valid Bearer authorization headers for the pre-seeded test user."""
    token = create_access_token(str(test_user.firebase_uid), {"email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="client")
def client_fixture(
    db_session: Session,
    mock_firebase: Callable[..., Any],
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database session and mocked Firebase."""
    def _override_get_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
