"""External recipe-provider adapters tested without network access."""

import asyncio
from typing import Any

import pytest

from app.services import ai_client
from app.services.ai_client import (
    SpoonacularProvider,
    TheMealDBProvider,
    get_ai_provider,
)
from app.services.local_recipe_provider import LocalRecipeProvider


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeAsyncClient:
    def __init__(self, responses: list[FakeResponse], **_: Any) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def get(
        self, url: str, params: dict[str, Any] | None = None
    ) -> FakeResponse:
        self.calls.append((url, params or {}))
        return self.responses.pop(0)


def test_spoonacular_maps_response_and_sends_pantry_and_allergy_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeAsyncClient(
        [
            FakeResponse(
                {
                    "results": [
                        {
                            "title": "Rice and vegetables",
                            "readyInMinutes": 25,
                            "servings": 2,
                            "extendedIngredients": [
                                {"original": "1 cup rice"},
                                {"original": "2 tomatoes"},
                            ],
                            "analyzedInstructions": [
                                {"steps": [{"step": "Cook the rice."}]}
                            ],
                            "nutrition": {
                                "nutrients": [{"name": "Calories", "amount": 385.2}]
                            },
                        }
                    ]
                }
            )
        ]
    )
    monkeypatch.setenv("SPOONACULAR_API_KEY", "test-key")
    monkeypatch.setattr(ai_client.httpx, "AsyncClient", lambda **kwargs: fake_client)
    prompt = (
        "Ingredientes en despensa: [arroz, tomate]. "
        "Alergias prohibidas: [Maní]. Debes crear una receta."
    )

    recipe = asyncio.run(SpoonacularProvider().generate_recipe(prompt))

    assert recipe.nombre == "Rice and vegetables"
    assert recipe.calorias == 385
    assert recipe.ingredientes == ["1 cup rice", "2 tomatoes"]
    assert recipe.pasos == ["Cook the rice."]
    _, params = fake_client.calls[0]
    assert params["includeIngredients"] == "arroz,tomate"
    assert params["excludeIngredients"] == "peanut,groundnut"
    assert params["intolerances"] == "peanut"
    assert params["apiKey"] == "test-key"


def test_spoonacular_skips_excluded_recipe_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeAsyncClient(
        [
            FakeResponse(
                {
                    "results": [
                        {"title": "Previous meal"},
                        {
                            "title": "New meal",
                            "extendedIngredients": [{"original": "rice"}],
                            "analyzedInstructions": [
                                {"steps": [{"step": "Cook."}]}
                            ],
                        },
                    ]
                }
            )
        ]
    )
    monkeypatch.setenv("SPOONACULAR_API_KEY", "test-key")
    monkeypatch.setattr(ai_client.httpx, "AsyncClient", lambda **kwargs: fake_client)

    recipe = asyncio.run(
        SpoonacularProvider().generate_recipe("Excluir la receta [Previous meal].")
    )

    assert recipe.nombre == "New meal"


def test_themealdb_looks_up_full_meal_and_maps_measures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meal = {
        "strMeal": "Tomato rice",
        "strInstructions": "Cook the rice.\nAdd the tomato.",
        "strIngredient1": "Rice",
        "strMeasure1": "1 cup",
        "strIngredient2": "Tomato",
        "strMeasure2": "2",
        "strIngredient3": "",
    }
    fake_client = FakeAsyncClient(
        [
            FakeResponse({"meals": [{"idMeal": "123", "strMeal": "Tomato rice"}]}),
            FakeResponse({"meals": [meal]}),
        ]
    )
    monkeypatch.setenv("THEMEALDB_API_KEY", "dev-key")
    monkeypatch.setattr(ai_client.httpx, "AsyncClient", lambda **kwargs: fake_client)
    monkeypatch.setattr(ai_client.random, "shuffle", lambda values: None)
    prompt = "Ingredientes en despensa: [tomato]. Alergias prohibidas: [Maní]."

    recipe = asyncio.run(TheMealDBProvider().generate_recipe(prompt))

    assert recipe.nombre == "Tomato rice"
    assert recipe.ingredientes == ["1 cup Rice", "2 Tomato"]
    assert recipe.pasos == ["Cook the rice.", "Add the tomato."]
    assert recipe.calorias == 0
    assert fake_client.calls[0] == (
        "https://www.themealdb.com/api/json/v1/dev-key/filter.php",
        {"i": "tomato"},
    )
    assert fake_client.calls[1][1] == {"i": "123"}


def test_themealdb_random_provider_skips_excluded_recipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeAsyncClient(
        [
            FakeResponse(
                {
                    "meals": [
                        {
                            "strMeal": "Previous meal",
                            "strInstructions": "Cook.",
                            "strIngredient1": "Rice",
                        }
                    ]
                }
            ),
            FakeResponse(
                {
                    "meals": [
                        {
                            "strMeal": "New meal",
                            "strInstructions": "Cook.",
                            "strIngredient1": "Tomato",
                        }
                    ]
                }
            ),
        ]
    )
    monkeypatch.setenv("THEMEALDB_API_KEY", "1")
    monkeypatch.setattr(ai_client.httpx, "AsyncClient", lambda **kwargs: fake_client)

    recipe = asyncio.run(
        TheMealDBProvider().generate_recipe("Excluir la receta [Previous meal].")
    )

    assert recipe.nombre == "New meal"
    assert len(fake_client.calls) == 2


@pytest.mark.parametrize(
    ("provider_name", "provider_type"),
    [
        ("local", LocalRecipeProvider),
        ("spoonacular", SpoonacularProvider),
        ("themealdb", TheMealDBProvider),
    ],
)
def test_provider_selection_from_environment(
    monkeypatch: pytest.MonkeyPatch, provider_name: str, provider_type: type
) -> None:
    monkeypatch.setenv("AI_PROVIDER", provider_name)

    assert isinstance(get_ai_provider(), provider_type)


def test_local_provider_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    assert isinstance(get_ai_provider(), LocalRecipeProvider)