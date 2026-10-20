"""Pruebas de aislamiento y persistencia de recetas favoritas."""

from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.security import get_current_user
from app.db.session import get_session
from app.main import app
from app.models.favorite_recipe import FavoriteRecipe
from app.models.user import User
from app.routers import recipes as recipes_router

test_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
_authenticated_user_id: UUID


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    global _authenticated_user_id
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        user_a = User(firebase_uid="favorite-a", email="favorite-a@example.com")
        user_b = User(firebase_uid="favorite-b", email="favorite-b@example.com")
        session.add_all([user_a, user_b])
        session.commit()
        session.refresh(user_a)
        session.refresh(user_b)
        _authenticated_user_id = user_a.id
        app.state.favorite_test_users = {"a": user_a.id, "b": user_b.id}

    def override_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    def override_user() -> User:
        with Session(test_engine) as session:
            return session.get(User, _authenticated_user_id)  # type: ignore[return-value]

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    yield TestClient(app)
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(test_engine)


def _recipe(name: str) -> dict[str, object]:
    return {
        "nombre": name,
        "tiempo_estimado_minutos": 20,
        "porciones": 2,
        "calorias": 345,
        "nutricion": {
            "calorias_kcal": 345,
            "proteinas_g": 8,
            "carbohidratos_g": 53.5,
            "grasas_g": 11,
        },
        "ingredientes": ["arroz", "espinaca"],
        "ingredientes_faltantes": [],
        "pasos": ["Cocinar y servir."],
        "apto_para_alergias": True,
    }


def test_create_favorite_returns_created_recipe(client: TestClient) -> None:
    response = client.post("/api/v1/recipes/favorites", json=_recipe("Bowl"))

    assert response.status_code == 201
    favorite = response.json()
    assert favorite["nombre"] == "Bowl"
    assert favorite["receta"]["ingredientes"] == ["arroz", "espinaca"]
    assert favorite["receta"]["nutricion"]["calorias_kcal"] == 345
    assert favorite["id"]
    assert favorite["fecha_guardado"]


def test_saving_same_recipe_twice_returns_existing_favorite(
    client: TestClient,
) -> None:
    first = client.post("/api/v1/recipes/favorites", json=_recipe("Bowl"))
    second = client.post("/api/v1/recipes/favorites", json=_recipe("Bowl"))

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    with Session(test_engine) as session:
        assert len(session.exec(select(FavoriteRecipe)).all()) == 1


def test_favorites_list_is_newest_first(client: TestClient) -> None:
    first = client.post("/api/v1/recipes/favorites", json=_recipe("First")).json()
    second = client.post("/api/v1/recipes/favorites", json=_recipe("Second")).json()
    with Session(test_engine) as session:
        oldest = session.get(FavoriteRecipe, UUID(first["id"]))
        newest = session.get(FavoriteRecipe, UUID(second["id"]))
        assert oldest is not None and newest is not None
        oldest.fecha_guardado = datetime(2025, 1, 1, tzinfo=timezone.utc)
        newest.fecha_guardado = datetime(2026, 1, 1, tzinfo=timezone.utc)
        session.add_all([oldest, newest])
        session.commit()

    response = client.get("/api/v1/recipes/favorites")

    assert [favorite["nombre"] for favorite in response.json()] == ["Second", "First"]


def test_favorites_persist_for_a_new_client_with_the_same_user(
    client: TestClient,
) -> None:
    created = client.post("/api/v1/recipes/favorites", json=_recipe("Persisted"))
    new_client = TestClient(app)

    response = new_client.get("/api/v1/recipes/favorites")

    assert response.status_code == 200
    assert response.json()[0]["id"] == created.json()["id"]


def test_get_favorite_does_not_call_recipe_provider(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = client.post("/api/v1/recipes/favorites", json=_recipe("Stored")).json()

    def fail_if_provider_is_used():
        pytest.fail("A favorite lookup must not invoke recipe generation.")

    monkeypatch.setattr(recipes_router, "get_ai_provider", fail_if_provider_is_used)
    response = client.get(f"/api/v1/recipes/favorites/{created['id']}")

    assert response.status_code == 200
    assert response.json()["receta"]["nombre"] == "Stored"


def test_delete_favorite_removes_it_from_the_list(client: TestClient) -> None:
    created = client.post("/api/v1/recipes/favorites", json=_recipe("Delete me")).json()

    response = client.delete(f"/api/v1/recipes/favorites/{created['id']}")

    assert response.status_code == 204
    assert client.get("/api/v1/recipes/favorites").json() == []


def test_user_cannot_view_or_delete_another_users_favorite(
    client: TestClient,
) -> None:
    global _authenticated_user_id
    created = client.post("/api/v1/recipes/favorites", json=_recipe("Private")).json()
    user_a_id = _authenticated_user_id
    _authenticated_user_id = app.state.favorite_test_users["b"]
    try:
        assert client.get("/api/v1/recipes/favorites").json() == []
        assert (
            client.get(f"/api/v1/recipes/favorites/{created['id']}").status_code == 404
        )
        assert (
            client.delete(f"/api/v1/recipes/favorites/{created['id']}").status_code
            == 404
        )
    finally:
        _authenticated_user_id = user_a_id


def test_favorites_require_authentication(client: TestClient) -> None:
    app.dependency_overrides.pop(get_current_user)

    assert client.get("/api/v1/recipes/favorites").status_code == 401
