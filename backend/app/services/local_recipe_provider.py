"""Zero-cost recipe retrieval from the project's locally authored corpus."""

from dataclasses import dataclass

from app.schemas.recipes import RecipeRead
from app.services.ai_client import (
    AIProvider,
    NoLocalRecipeError,
    _context_values,
    _excluded_recipe_names,
)
from app.services.allergen_filter import (
    AllergenDetectedException,
    validate_recipe_ingredients,
)
from app.services.ingredient_catalog import classify_ingredient, normalize_ingredient


@dataclass(frozen=True)
class LocalRecipe:
    """Wrapper for one immutable recipe entry in the locally authored corpus."""

    recipe: RecipeRead


LOCAL_RECIPES = (
    LocalRecipe(
        RecipeRead(
            nombre="Bowl de arroz y verduras",
            tiempo_estimado_minutos=20,
            porciones=2,
            calorias=0,
            ingredientes=["arroz", "tomate", "espinaca", "cebolla", "aceite de oliva"],
            pasos=[
                "Cocina el arroz en agua hasta que quede tierno.",
                "Saltea la cebolla, el tomate y la espinaca con aceite.",
                "Sirve las verduras sobre el arroz.",
            ],
            apto_para_alergias=True,
        )
    ),
    LocalRecipe(
        RecipeRead(
            nombre="Lentejas con verduras",
            tiempo_estimado_minutos=35,
            porciones=3,
            calorias=0,
            ingredientes=["lentejas", "zanahoria", "tomate", "cebolla", "ajo"],
            pasos=[
                "Enjuaga las lentejas y ponlas a cocer en agua.",
                "Agrega zanahoria, tomate, cebolla y ajo picados.",
                "Cocina a fuego medio hasta que las lentejas estén suaves.",
            ],
            apto_para_alergias=True,
        )
    ),
    LocalRecipe(
        RecipeRead(
            nombre="Ensalada de garbanzos",
            tiempo_estimado_minutos=15,
            porciones=2,
            calorias=0,
            ingredientes=["garbanzos", "pepino", "tomate", "limón", "aceite de oliva"],
            pasos=[
                "Escurre y enjuaga los garbanzos cocidos.",
                "Corta el pepino y el tomate en cubos.",
                "Mezcla todo con limón y aceite de oliva.",
            ],
            apto_para_alergias=True,
        )
    ),
    LocalRecipe(
        RecipeRead(
            nombre="Avena con banana y canela",
            tiempo_estimado_minutos=10,
            porciones=1,
            calorias=0,
            ingredientes=["avena", "banana", "canela", "agua"],
            pasos=[
                "Calienta la avena con agua durante unos minutos.",
                "Agrega banana en rodajas y una pizca de canela.",
            ],
            apto_para_alergias=True,
        )
    ),
    LocalRecipe(
        RecipeRead(
            nombre="Papas salteadas con pimiento",
            tiempo_estimado_minutos=25,
            porciones=2,
            calorias=0,
            ingredientes=["papa", "pimiento", "cebolla", "aceite de oliva"],
            pasos=[
                "Corta las papas y cocínalas en agua hasta que empiecen a suavizarse.",
                "Saltea la cebolla y el pimiento con aceite.",
                "Agrega las papas y cocina hasta dorar.",
            ],
            apto_para_alergias=True,
        )
    ),
    LocalRecipe(
        RecipeRead(
            nombre="Tacos sencillos de frijoles y maíz",
            tiempo_estimado_minutos=20,
            porciones=2,
            calorias=0,
            ingredientes=["frijoles", "maíz", "tomate", "cebolla", "limón"],
            pasos=[
                "Calienta los frijoles cocidos y el maíz en una sartén.",
                "Sirve con tomate y cebolla picados.",
                "Agrega unas gotas de limón antes de servir.",
            ],
            apto_para_alergias=True,
        )
    ),
    LocalRecipe(
        RecipeRead(
            nombre="Pasta con tomate y ajo",
            tiempo_estimado_minutos=25,
            porciones=2,
            calorias=0,
            ingredientes=["pasta de trigo", "tomate", "ajo", "aceite de oliva"],
            pasos=[
                "Cuece la pasta siguiendo las instrucciones del paquete.",
                "Cocina el tomate y el ajo picados con aceite.",
                "Mezcla la salsa con la pasta escurrida.",
            ],
            apto_para_alergias=True,
        )
    ),
)


class LocalRecipeProvider(AIProvider):
    """Retrieve a recipe without network calls or a hosted generative model.

    The prompt carries the user's pantry, allergies, and optional excluded title.
    Candidates must pass allergy checks and, when pantry items exist, match at
    least one classified pantry ingredient. Ranking is by number of pantry
    matches; ties keep the corpus order. This is catalog retrieval, not free-form
    recipe synthesis, so corpus coverage limits what can be suggested.
    """

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        pantry = _context_values(prompt, "Ingredientes en despensa")
        allergies = _context_values(prompt, "Alergias prohibidas")
        excluded = {
            normalize_ingredient(name) for name in _excluded_recipe_names(prompt)
        }

        candidates: list[tuple[int, LocalRecipe]] = []
        for local_recipe in LOCAL_RECIPES:
            recipe = local_recipe.recipe
            if normalize_ingredient(recipe.nombre) in excluded:
                continue
            allergy_labels = {
                normalize_ingredient(allergy) for allergy in allergies
            }
            classified_allergens = {
                normalize_ingredient(allergen)
                for ingredient in recipe.ingredientes
                if (classification := classify_ingredient(ingredient)) is not None
                for allergen in classification.allergens
            }
            if classified_allergens & allergy_labels:
                continue
            try:
                validate_recipe_ingredients(recipe.ingredientes, allergies)
            except AllergenDetectedException:
                continue

            if pantry:
                matched = sum(
                    1
                    for pantry_item in pantry
                    if _matches_recipe(pantry_item, recipe.ingredientes)
                )
                if matched == 0:
                    continue
                candidates.append((matched, local_recipe))
            else:
                candidates.append((0, local_recipe))

        if not candidates:
            raise NoLocalRecipeError(
                "No hay una receta local compatible con la despensa y las restricciones."
            )
        candidates.sort(key=lambda candidate: candidate[0], reverse=True)
        return candidates[0][1].recipe.model_copy(deep=True)


def _matches_recipe(pantry_item: str, ingredients: list[str]) -> bool:
    """Compare pantry and recipe items by canonical taxonomy identity.

    Unknown pantry names only match an exactly normalized recipe ingredient;
    loose substring matching could incorrectly treat `salt` as part of `salmon`.
    """
    pantry_classification = classify_ingredient(pantry_item)
    if pantry_classification is None:
        return any(
            normalize_ingredient(pantry_item) == normalize_ingredient(ingredient)
            for ingredient in ingredients
        )
    return any(
        (classification := classify_ingredient(ingredient)) is not None
        and classification.canonical == pantry_classification.canonical
        for ingredient in ingredients
    )