"""Deterministic checks that prevent prohibited allergens in recipes."""

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
    """Raised when a recipe ingredient contains a prohibited allergen."""

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
    """Reject a recipe when an ingredient contains an allergy label or known alias.

    Text is case-folded, stripped of diacritics and non-alphanumeric characters,
    then compared using substring matching. The alias table improves matching
    across Spanish/English names, but it is finite and cannot detect hidden
    ingredients, brand-specific compounds, traces, or cross-contamination.
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