"""Provider-neutral asynchronous interface for recipe language models."""

import json
import os
import random
import re
import unicodedata
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.schemas.recipes import RecipeRead


class AIProvider(ABC):
    """Common asynchronous contract for local, mock, and external providers."""

    @abstractmethod
    async def generate_recipe(self, prompt: str) -> RecipeRead:
        """Generate one recipe from the assembled system prompt."""


class MockProvider(AIProvider):
    """Return one fixed example; intended for tests and demos only."""

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        del prompt
        return RecipeRead(
            nombre="Bowl de arroz y verduras",
            tiempo_estimado_minutos=20,
            porciones=2,
            calorias=420,
            ingredientes=["arroz", "tomate", "espinaca", "aceite de oliva"],
            pasos=["Cocina el arroz.", "Saltea las verduras y sirve sobre el arroz."],
            apto_para_alergias=True,
        )


class APIProvider(AIProvider):
    """Call an OpenAI-compatible chat API using environment-only credentials.

    Configure `AI_API_URL`, `AI_API_KEY`, and `AI_MODEL`. The model must return
    the recipe JSON contract; the router still applies local allergy validation.
    """

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        api_key = os.getenv("AI_API_KEY", "")
        api_url = os.getenv("AI_API_URL", "")
        if not api_key or not api_url:
            raise RuntimeError("AI_API_KEY y AI_API_URL deben estar configuradas.")

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("AI_MODEL", ""),
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"{prompt}\nResponde únicamente con un JSON válido "
                                "que cumpla el contrato de receta solicitado."
                            ),
                        }
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()

        payload: dict[str, Any] = response.json()
        content = payload["choices"][0]["message"]["content"]
        return RecipeRead.model_validate(json.loads(content))


class RecipeProviderError(RuntimeError):
    """Provider-level failure translated by the HTTP router to status 502."""


class NoLocalRecipeError(RecipeProviderError):
    """Raised when the local corpus has no recipe matching pantry and restrictions."""


def _context_values(prompt: str, label: str) -> list[str]:
    """Read a bracketed value list from the stable context prompt format."""
    match = re.search(rf"{re.escape(label)}: \[([^\]]*)\]", prompt)
    if not match:
        return []
    return [value.strip() for value in match.group(1).split(",") if value.strip()]


def _excluded_recipe_names(prompt: str) -> list[str]:
    """Extract titles supplied by the client through its generate-another option."""
    return re.findall(r"Excluir la receta \[([^\]]+)\]", prompt, flags=re.IGNORECASE)


def _extra_exclusions(prompt: str) -> list[str]:
    """Extract allergen and ingredient feedback added after an unsafe result."""
    return re.findall(
        r"no incluyas el alérgeno ([^ ]+) ni el ingrediente ([^.]+)",
        prompt,
        flags=re.IGNORECASE,
    )


def _allergen_terms(allergies: list[str]) -> list[str]:
    """Map Spanish allergy labels to search terms understood by external APIs."""
    mapped = {
        "gluten": ("gluten", "wheat", "barley", "rye"),
        "lacteos": ("dairy", "milk", "cheese", "butter", "yogurt"),
        "huevos": ("egg",),
        "mani": ("peanut", "groundnut"),
        "frutossecos": ("tree nut", "almond", "walnut", "cashew", "hazelnut"),
        "soya": ("soy", "soya"),
        "pescado": ("fish", "salmon", "tuna", "cod"),
        "mariscos": ("shellfish", "shrimp", "crab", "lobster", "mussel"),
    }
    terms: list[str] = []
    for allergy in allergies:
        normalized = "".join(
            character
            for character in unicodedata.normalize("NFKD", allergy.casefold())
            if not unicodedata.combining(character)
        )
        normalized = "".join(character for character in normalized if character.isalnum())
        terms.extend(mapped.get(normalized, [allergy]))
    return list(dict.fromkeys(terms))


class SpoonacularProvider(AIProvider):
    """Search Spoonacular and normalize its structured result to `RecipeRead`.

    It requires `SPOONACULAR_API_KEY`, and calls consume account quota. Search
    filters improve retrieval but do not replace the backend allergen check.
    """

    base_url = "https://api.spoonacular.com"

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        api_key = os.getenv("SPOONACULAR_API_KEY", "")
        if not api_key:
            raise RecipeProviderError("SPOONACULAR_API_KEY no está configurada.")

        pantry = _context_values(prompt, "Ingredientes en despensa")
        allergies = _context_values(prompt, "Alergias prohibidas")
        exclusions = _allergen_terms(allergies)
        for _, ingredient in _extra_exclusions(prompt):
            exclusions.append(ingredient.strip())
        params: dict[str, Any] = {
            "apiKey": api_key,
            "number": 10,
            "addRecipeInformation": "true",
            "addRecipeInstructions": "true",
            "addRecipeNutrition": "true",
            "instructionsRequired": "true",
        }
        if pantry:
            params["includeIngredients"] = ",".join(pantry)
        if exclusions:
            params["excludeIngredients"] = ",".join(dict.fromkeys(exclusions))
        if allergies:
            intolerance_map = {
                "gluten": "gluten",
                "lacteos": "dairy",
                "huevos": "egg",
                "mani": "peanut",
                "frutossecos": "tree nut",
                "soya": "soy",
                "pescado": "seafood",
                "mariscos": "shellfish",
            }
            params["intolerances"] = ",".join(
                intolerance_map.get(
                    "".join(
                        character
                        for character in unicodedata.normalize(
                            "NFKD", allergy.casefold()
                        )
                        if not unicodedata.combining(character)
                    ).replace(" ", ""),
                    allergy,
                )
                for allergy in allergies
            )

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.get(
                    f"{self.base_url}/recipes/complexSearch", params=params
                )
                response.raise_for_status()
            results = response.json().get("results", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise RecipeProviderError("No se pudo consultar Spoonacular.") from exc

        excluded_names = {name.casefold() for name in _excluded_recipe_names(prompt)}
        recipe_data = next(
            (
                item
                for item in results
                if str(item.get("title", "")).casefold() not in excluded_names
            ),
            None,
        )
        if not recipe_data:
            raise RecipeProviderError("Spoonacular no encontró recetas disponibles.")
        return _spoonacular_recipe(recipe_data)


def _spoonacular_recipe(data: dict[str, Any]) -> RecipeRead:
    """Translate Spoonacular ingredients, steps, and nutrition to our schema."""
    ingredients = [
        str(item.get("original") or item.get("name", "")).strip()
        for item in data.get("extendedIngredients", [])
    ]
    if not ingredients:
        ingredients = [
            str(item.get("name", "")).strip()
            for item in data.get("usedIngredients", []) + data.get("missedIngredients", [])
        ]
    steps = [
        str(step.get("step", "")).strip()
        for instruction in data.get("analyzedInstructions", [])
        for step in instruction.get("steps", [])
        if step.get("step")
    ]
    calories = next(
        (
            int(round(nutrient.get("amount", 0)))
            for nutrient in data.get("nutrition", {}).get("nutrients", [])
            if nutrient.get("name", "").casefold() == "calories"
        ),
        0,
    )
    return RecipeRead(
        nombre=str(data.get("title") or "Receta"),
        tiempo_estimado_minutos=max(1, int(data.get("readyInMinutes") or 30)),
        porciones=max(1, int(data.get("servings") or 1)),
        calorias=max(0, calories),
        ingredientes=[ingredient for ingredient in ingredients if ingredient],
        pasos=steps or ["Consulta las instrucciones de preparación de la receta."],
        apto_para_alergias=True,
    )


class TheMealDBProvider(AIProvider):
    """Discover and look up meals through TheMealDB's V1 JSON API.

    The development key defaults to `1`; public apps need appropriate access.
    Its free filter accepts one pantry ingredient. The response has no verified
    calories or preparation time, so the schema uses zero calories (unknown) and
    a 30-minute estimate.
    """

    base_url = "https://www.themealdb.com/api/json/v1"

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        api_key = os.getenv("THEMEALDB_API_KEY", "1")
        base_url = f"{self.base_url}/{api_key}"
        pantry = _context_values(prompt, "Ingredientes en despensa")
        excluded_names = {
            name.casefold() for name in _excluded_recipe_names(prompt)
        }
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                if pantry:
                    response = await client.get(
                        f"{base_url}/filter.php", params={"i": pantry[0]}
                    )
                    response.raise_for_status()
                    candidates = response.json().get("meals") or []
                    if not candidates:
                        raise RecipeProviderError(
                            "TheMealDB no encontró recetas para la despensa."
                        )
                    random.shuffle(candidates)
                    for candidate in candidates:
                        detail_response = await client.get(
                            f"{base_url}/lookup.php",
                            params={"i": candidate["idMeal"]},
                        )
                        detail_response.raise_for_status()
                        meals = detail_response.json().get("meals") or []
                        if meals and str(meals[0].get("strMeal", "")).casefold() not in excluded_names:
                            return _themealdb_recipe(meals[0])
                    raise RecipeProviderError(
                        "TheMealDB no encontró otra receta disponible."
                    )

                for _ in range(5):
                    response = await client.get(f"{base_url}/random.php")
                    response.raise_for_status()
                    meals = response.json().get("meals") or []
                    if not meals:
                        continue
                    if str(meals[0].get("strMeal", "")).casefold() in excluded_names:
                        continue
                    return _themealdb_recipe(meals[0])
                raise RecipeProviderError(
                    "TheMealDB no encontró una receta distinta a la excluida."
                )
        except RecipeProviderError:
            raise
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise RecipeProviderError("No se pudo consultar TheMealDB.") from exc


def _themealdb_recipe(data: dict[str, Any]) -> RecipeRead:
    """Pair numbered ingredient/measure fields and split instruction text."""
    ingredients: list[str] = []
    for index in range(1, 21):
        ingredient = str(data.get(f"strIngredient{index}") or "").strip()
        measure = str(data.get(f"strMeasure{index}") or "").strip()
        if ingredient:
            ingredients.append(f"{measure} {ingredient}".strip())
    instruction_text = str(data.get("strInstructions") or "")
    steps = [step.strip() for step in instruction_text.splitlines() if step.strip()]
    if len(steps) <= 1 and instruction_text:
        steps = [
            step.strip()
            for step in re.split(r"(?<=[.!?])\s+", instruction_text)
            if step.strip()
        ]
    return RecipeRead(
        nombre=str(data.get("strMeal") or "Receta"),
        tiempo_estimado_minutos=30,
        porciones=2,
        calorias=0,
        ingredientes=ingredients,
        pasos=steps or ["Consulta la fuente para ver las instrucciones de preparación."],
        apto_para_alergias=True,
    )


def get_ai_provider() -> AIProvider:
    """Resolve `AI_PROVIDER`, defaulting to the offline local recipe corpus.

    Supported values are `local`, `mock`, `api`, `spoonacular`, and `themealdb`
    (also `mealdb`). Only the selected external provider reads its credentials.
    """
    provider = os.getenv("AI_PROVIDER", "local").strip().lower()
    if provider == "local":
        from app.services.local_recipe_provider import LocalRecipeProvider

        return LocalRecipeProvider()
    if provider == "mock":
        return MockProvider()
    if provider == "api":
        return APIProvider()
    if provider == "spoonacular":
        return SpoonacularProvider()
    if provider in {"themealdb", "mealdb"}:
        return TheMealDBProvider()
    raise ValueError(f"AI_PROVIDER no reconocido: {provider}")