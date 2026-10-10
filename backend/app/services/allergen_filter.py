"""checks deterministas que prohiben alergenos en las recetas"""

import unicodedata
from collections.abc import Iterable

ALLERGEN_ALIASES = {
    "gluten": ("wheat", "trigo", "barley", "cebada", "rye", "centeno", "semolina", "durum", "malt"),
    "lacteos": ("dairy", "milk", "leche", "cheese", "queso", "butter", "mantequilla", "yogurt", "yogur", "cream", "crema", "whey"),
    "huevos": ("egg", "eggs", "huevo", "albumin", "mayonnaise"),
    "mani": ("peanut", "groundnut", "cacahuate"),
    "frutossecos": (
        "tree nut",
        "almond",
        "walnut",
        "cashew",
        "hazelnut",
        "pistachio",
        "pecan",
        "macadamia",
        "nuez",
        "almendra",
    ),
    "soya": ("soy", "soja", "soybean", "tofu", "tempeh", "edamame"),
    "pescado": (
        "fish",
        "salmon",
        "tuna",
        "cod",
        "anchovy",
        "sardine",
        "trout",
        "atun",
    ),
    "mariscos": (
        "shellfish",
        "shrimp",
        "prawn",
        "crab",
        "lobster",
        "mussel",
        "oyster",
        "scallop",
        "camaron",
    ),
}


class AllergenDetectedException(Exception):
    """cuando un ingrediente de la receta contiene un alergeno prohibido"""

    def __init__(self, allergen: str, ingredient: str) -> None:
        self.allergen = allergen
        self.ingredient = ingredient
        super().__init__(f"El ingrediente '{ingredient}' contiene '{allergen}'.")


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_diacritics = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return "".join(character for character in without_diacritics if character.isalnum())


def validate_recipe_ingredients(
    ingredients: Iterable[str], allergies: Iterable[str]
) -> None:
    """
    rechaza una receta cuando un ingrediente contiene una etiqueta de alergia o un alias desconocido
    el texto se divide en mayus y minus, se eliminan diacriticos y caracteres no alfanumericos, luego se compara
    con la coincidencia de subcadenas, la tabla de alias mejora la coincidencia entre nombres en ingles y español
    mas es finita y no puede detectar ingredientes ocultos y compuestos especificos de la marca, trazas o contaminacion
    cruzada. 
    """
    normalized_allergies: list[tuple[str, str]] = []
    for allergy in allergies:
        normalized = _normalize(allergy)
        if normalized:
            normalized_allergies.append((allergy, normalized))
            aliases = ALLERGEN_ALIASES.get(normalized, ())
            normalized_allergies.extend(
                (allergy, _normalize(alias)) for alias in aliases
            )

    for ingredient in ingredients:
        normalized_ingredient = _normalize(ingredient)
        for allergy, normalized_allergy in normalized_allergies:
            if normalized_allergy in normalized_ingredient:
                raise AllergenDetectedException(allergy, ingredient)