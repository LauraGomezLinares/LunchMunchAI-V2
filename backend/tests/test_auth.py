"""Authentication API tests with Firebase claims mocked at the boundary."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.services import auth_service

test_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    SQLModel.metadata.create_all(test_engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(
        auth_service,
        "verify_firebase_token",
        lambda _: {"uid": "firebase-1", "email": "user@example.com", "name": "Ana"},
    )
    yield TestClient(app)
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(test_engine)


def test_register_success(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"id_token": "valid"})
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "user@example.com"


def test_invalid_email_claim(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        auth_service,
        "verify_firebase_token",
        lambda _: {"uid": "bad", "email": "invalid"},
    )
    response = client.post("/api/v1/auth/register", json={"id_token": "valid"})
    assert response.status_code == 422


def test_duplicate_email(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client.post("/api/v1/auth/register", json={"id_token": "first"})
    monkeypatch.setattr(
        auth_service,
        "verify_firebase_token",
        lambda _: {"uid": "firebase-2", "email": "user@example.com"},
    )
    response = client.post("/api/v1/auth/register", json={"id_token": "second"})
    assert response.status_code == 409


def test_invalid_credentials(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject(_: str) -> dict[str, str]:
        raise HTTPException(
            status_code=401, detail="El token de Firebase no es válido o ha expirado."
        )

    monkeypatch.setattr(auth_service, "verify_firebase_token", reject)
    response = client.post("/api/v1/auth/login", json={"id_token": "bad"})
    assert response.status_code == 401


def test_password_is_not_stored(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"id_token": "valid"})
    assert response.status_code == 201
    with Session(test_engine) as session:
        assert session.exec(select(User)).one().hashed_password is None


def test_me_without_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_token(client: TestClient) -> None:
    login = client.post("/api/v1/auth/firebase-login", json={"id_token": "valid"})
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_me_with_invalid_token(client: TestClient) -> None:
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
