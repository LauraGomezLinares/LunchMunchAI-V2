"""Recipe generation API tests for context, timeouts, and allergen retries."""

import asyncio
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.security import get_current_user
from app.db.session import get_session
from app.main import app
from app.models.pantry import PantryItem
from app.models.user import User
from app.schemas.recipes import RecipeRead
from app.services.ai_client import MockProvider
from app.services import context_builder
from app.routers import recipes as recipes_router

test_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        user = User(
            firebase_uid="recipes-test",
            email="recipes@example.com",
            nombre="Chef",
            alergias=["Maní"],
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


def test_generate_recipe_uses_mock_provider(client: TestClient) -> None:
    response = client.post("/api/v1/recipes/generate")

    assert response.status_code == 200
    recipe = response.json()
    assert recipe["nombre"] == "Bowl de arroz y verduras"
    assert recipe["apto_para_alergias"] is True
    assert set(recipe) == {
        "nombre",
        "tiempo_estimado_minutos",
        "porciones",
        "calorias",
        "ingredientes",
        "pasos",
        "apto_para_alergias",
    }


def test_generate_recipe_timeout_returns_504(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class SlowProvider:
        async def generate_recipe(self, prompt: str) -> RecipeRead:
            del prompt
            await asyncio.sleep(0.05)
            return await MockProvider().generate_recipe("")

    monkeypatch.setattr(recipes_router, "get_ai_provider", lambda: SlowProvider())
    monkeypatch.setattr(recipes_router, "GENERATION_TIMEOUT_SECONDS", 0.001)

    response = client.post("/api/v1/recipes/generate")

    assert response.status_code == 504
    assert response.json()["detail"] == (
        "El chef está pensando demasiado, intenta nuevamente."
    )


def test_unsafe_recipe_retries_then_returns_safe_recipe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(test_engine) as session:
        user = session.exec(select(User)).one()
        session.add(
            PantryItem(
                ingrediente="Arroz",
                cantidad=1,
                unidad="kg",
                usuario_id=user.id,
            )
        )
        session.commit()

    class RetryProvider:
        def __init__(self) -> None:
            self.prompts: list[str] = []
            self.calls = 0

        async def generate_recipe(self, prompt: str) -> RecipeRead:
            self.prompts.append(prompt)
            self.calls += 1
            ingredients = ["mantequilla de maní"] if self.calls == 1 else ["arroz"]
            return RecipeRead(
                nombre="Receta de prueba",
                tiempo_estimado_minutos=10,
                porciones=1,
                calorias=100,
                ingredientes=ingredients,
                pasos=["Preparar."],
                apto_para_alergias=True,
            )

    provider = RetryProvider()
    monkeypatch.setattr(recipes_router, "get_ai_provider", lambda: provider)

    response = client.post(
        "/api/v1/recipes/generate", json={"excluir_receta": "Sopa anterior"}
    )

    assert response.status_code == 200
    assert provider.calls == 2
    assert all("Excluir la receta [Sopa anterior]" in p for p in provider.prompts)
    assert "Alergias prohibidas: [Maní]" in provider.prompts[0]


def test_three_unsafe_recipes_return_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class UnsafeProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_recipe(self, prompt: str) -> RecipeRead:
            del prompt
            self.calls += 1
            return RecipeRead(
                nombre="Insegura",
                tiempo_estimado_minutos=10,
                porciones=1,
                calorias=100,
                ingredientes=["mantequilla de maní"],
                pasos=["Preparar."],
                apto_para_alergias=True,
            )

    provider = UnsafeProvider()
    monkeypatch.setattr(recipes_router, "get_ai_provider", lambda: provider)

    response = client.post("/api/v1/recipes/generate")

    assert response.status_code == 422
    assert provider.calls == 3
    assert response.json()["detail"] == recipes_router.UNSAFE_RECIPE_MESSAGE


def test_context_builder_uses_exact_empty_pantry_fallback(client: TestClient) -> None:
    with Session(test_engine) as session:
        user = session.exec(select(User)).one()
        prompt = context_builder.build_recipe_context(session, user.id)

    assert prompt == context_builder.EMPTY_PANTRY_PROMPT


def test_context_builder_includes_pantry_and_allergies(client: TestClient) -> None:
    with Session(test_engine) as session:
        user = session.exec(select(User)).one()
        session.add(
            PantryItem(
                ingrediente="Arroz",
                cantidad=1,
                unidad="kg",
                usuario_id=user.id,
            )
        )
        session.commit()
        prompt = context_builder.build_recipe_context(session, user.id)

    assert prompt == (
        "Ingredientes en despensa: [Arroz]. Alergias prohibidas: [Maní]. "
        "Debes crear una receta que use la despensa y JAMÁS incluya las alergias."
    )