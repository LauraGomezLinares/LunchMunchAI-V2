"""Unit tests for deterministic allergen detection."""

import pytest

from app.services.allergen_filter import (
    AllergenDetectedException,
    validate_recipe_ingredients,
)


@pytest.mark.parametrize(
    ("ingredients", "allergies"),
    [
        (["maní"], ["Maní"]),
        (["Mantequilla de maní"], ["maní"]),
        (["Proteína de GLUTEN"], ["gluten"]),
        (["Queso añejo"], ["ANeJO"]),
        (["Salsa-de-SOYA"], ["soya"]),
    ],
)
def test_detects_exact_partial_and_normalized_matches(
    ingredients: list[str], allergies: list[str]
) -> None:
    with pytest.raises(AllergenDetectedException):
        validate_recipe_ingredients(ingredients, allergies)


@pytest.mark.parametrize(
    ("ingredients", "allergies"),
    [
        (["arroz", "tomate", "aceite de oliva"], ["maní", "gluten"]),
        (["leche"], []),
        (["maní"], [""]),
        (["  !!!  "], [" "]),
    ],
)
def test_allows_ingredients_without_nonempty_matches(
    ingredients: list[str], allergies: list[str]
) -> None:
    validate_recipe_ingredients(ingredients, allergies)


def test_exception_identifies_matching_allergen_and_ingredient() -> None:
    with pytest.raises(AllergenDetectedException) as error:
        validate_recipe_ingredients(["Mantequilla de maní"], ["Maní"])

    assert error.value.allergen == "Maní"
    assert error.value.ingredient == "Mantequilla de maní"