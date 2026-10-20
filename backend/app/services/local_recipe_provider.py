"""Recuperación de recetas sin coste alguno a partir del corpus de recetas creadas localmente por el proyecto."""

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
    """Wrapper para una entrada de receta inmutable en el corpus de autoría local."""

    recipe: RecipeRead


LOCAL_RECIPES = (
    LocalRecipe(
        RecipeRead(
            nombre="Bowl de arroz y verduras",
            tiempo_estimado_minutos=20,
            porciones=2,
            calorias=0,
            ingredientes=[
                "arroz",
                "tomate",
                "espinaca",
                "cebolla",
                "leche",
                "aceite de oliva",
            ],
            pasos=[
                "Cocina el arroz en agua hasta que quede tierno.",
                "Saltea la cebolla, el tomate y la espinaca con aceite.",
                "Agrega leche para ligar las verduras y sírvelas sobre el arroz.",
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
            ingredientes=[
                "lentejas",
                "zanahoria",
                "tomate",
                "cebolla",
                "ajo",
                "espinaca",
            ],
            pasos=[
                "Enjuaga las lentejas y ponlas a cocer en agua.",
                "Agrega zanahoria, tomate, cebolla y ajo picados.",
                "Cocina a fuego medio hasta que las lentejas estén suaves.",
                "Incorpora la espinaca al final y deja que se marchite.",
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
    """Recupera una receta sin llamadas a la red ni un modelo generativo alojado.
    La solicitud incluye la despensa del usuario, sus alergias y, opcionalmente, un título excluido.

    Las recetas candidatas deben superar las comprobaciones de alergias y, si existen ingredientes en la despensa, coincidir 
    conal menos un ingrediente clasificado. La clasificación se basa en el número de coincidencias con la despensa; en 
    caso de empate, se mantiene el orden del corpus. Se trata de una recuperación de catálogo, no de una síntesis de recetas 
    de formato libre,por lo que la cobertura del corpus limita las sugerencias.
    """

    async def generate_recipe(self, prompt: str) -> RecipeRead:
        pantry = _context_values(prompt, "Ingredientes en despensa")
        expiring = _context_values(
            prompt, "Ingredientes próximos a vencer (priorízalos)"
        )
        allergies = _context_values(prompt, "Alergias prohibidas")
        excluded = {
            normalize_ingredient(name) for name in _excluded_recipe_names(prompt)
        }

        candidates: list[tuple[int, int, LocalRecipe]] = []
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
                expiring_matched = sum(
                    1
                    for pantry_item in expiring
                    if _matches_recipe(pantry_item, recipe.ingredientes)
                )
                if matched == 0:
                    continue
                candidates.append((expiring_matched, matched, local_recipe))
            else:
                candidates.append((0, 0, local_recipe))

        if not candidates:
            raise NoLocalRecipeError(
                "No hay una receta local compatible con la despensa y las restricciones."
            )
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
        return candidates[0][2].recipe.model_copy(deep=True)


def _matches_recipe(pantry_item: str, ingredients: list[str]) -> bool:
    """Compara los artículos de la despensa y de las recetas según su taxonomía canónica.

    Los nombres desconocidos de la despensa solo coinciden con un ingrediente de la receta normalizado con exactitud;

    la coincidencia de subcadenas menos precisa podría tratar incorrectamente la «sal» como parte del «salmón».
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