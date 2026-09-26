"""Deterministic checks that prevent prohibited allergens in recipes."""

import unicodedata
from collections.abc import Iterable


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
    """Raise on any normalized substring match between ingredients and allergies."""
    normalized_allergies = [
        (allergy, _normalize(allergy))
        for allergy in allergies
        if _normalize(allergy)
    ]

    for ingredient in ingredients:
        normalized_ingredient = _normalize(ingredient)
        for allergy, normalized_allergy in normalized_allergies:
            if normalized_allergy in normalized_ingredient:
                raise AllergenDetectedException(allergy, ingredient)