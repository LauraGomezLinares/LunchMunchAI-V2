"""Pantry API tests with mocked Firebase auth."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.security import get_current_user
from app.db.session import get_session
from app.main import app
from app.models.pantry import PantryItem  # noqa: F401
from app.models.user import User

test_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    SQLModel.metadata.create_all(test_engine)

    def override_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    def override_user() -> User:
        with Session(test_engine) as session:
            user = session.exec(
                __import__("sqlmodel").select(User)
            ).first()
            if not user:
                user = User(
                    firebase_uid="test-uid",
                    email="test@mealmuse.com",
                    nombre="Test User",
                )
                session.add(user)
                session.commit()
                session.refresh(user)
            return user

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    yield TestClient(app)
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(test_engine)


def test_create_pantry_item(client: TestClient) -> None:
    response = client.post(
        "/api/v1/pantry/",
        json={
            "ingrediente": "Espinaca",
            "cantidad": 300,
            "unidad": "g",
        },
    )
    assert response.status_code == 201
    assert response.json()["ingrediente"] == "Espinaca"
    assert response.json()["cantidad"] == 300


def test_list_pantry_empty(client: TestClient) -> None:
    response = client.get("/api/v1/pantry/")
    assert response.status_code == 200
    assert response.json() == []


def test_update_pantry_item(client: TestClient) -> None:
    created = client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Huevos", "cantidad": 6, "unidad": "unidades"},
    ).json()
    response = client.put(
        f"/api/v1/pantry/{created['id']}",
        json={"cantidad": 4},
    )
    assert response.status_code == 200
    assert response.json()["cantidad"] == 4


def test_delete_pantry_item(client: TestClient) -> None:
    created = client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Leche", "cantidad": 1, "unidad": "L"},
    ).json()
    response = client.delete(f"/api/v1/pantry/{created['id']}")
    assert response.status_code == 204