"""Profile API tests for authenticated reads and partial allergy updates."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.security import get_current_user
from app.db.session import get_session
from app.main import app
from app.models.user import User

test_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        user = User(
            firebase_uid="profile-test",
            email="profile@example.com",
            nombre="Perfil",
            objetivos_nutricionales="Más proteína",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    def override_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    def override_user() -> User:
        with Session(test_engine) as session:
            return session.get(User, user_id)  # type: ignore[return-value]

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    yield TestClient(app)
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(test_engine)


def test_get_profile_includes_allergies_and_nutrition_objectives(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/users/profile")

    assert response.status_code == 200
    assert response.json()["alergias"] == []
    assert response.json()["objetivos_nutricionales"] == "Más proteína"


def test_put_profile_updates_only_allergies(client: TestClient) -> None:
    allergies = [
        "Gluten",
        "Lácteos",
        "Huevos",
        "Maní",
        "Frutos secos",
        "Soya",
        "Pescado",
        "Mariscos",
    ]
    response = client.put(
        "/api/v1/users/profile", json={"alergias": allergies}
    )

    assert response.status_code == 200
    assert response.json()["alergias"] == allergies
    assert response.json()["objetivos_nutricionales"] == "Más proteína"
    with Session(test_engine) as session:
        user = session.exec(select(User)).one()
        assert user.alergias == allergies


def test_put_profile_rejects_allergies_outside_catalog(client: TestClient) -> None:
    response = client.put(
        "/api/v1/users/profile", json={"alergias": ["Polen", "Gluten"]}
    )

    assert response.status_code == 422


def test_put_profile_requires_only_allergies(client: TestClient) -> None:
    response = client.put("/api/v1/users/profile", json={"alergias": []})

    assert response.status_code == 200
