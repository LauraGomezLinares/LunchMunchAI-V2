"""Tests for local ingredient canonicalization and classification."""

from app.services.ingredient_catalog import classify_ingredient


def test_classifies_spanish_and_english_aliases() -> None:
    tomato = classify_ingredient("Tomates frescos")
    rice = classify_ingredient("brown rice")

    assert tomato is not None
    assert tomato.canonical == "tomate"
    assert tomato.category == "verdura"
    assert rice is not None
    assert rice.canonical == "arroz"
    assert rice.category == "cereal"


def test_classifies_allergen_labels_from_catalog() -> None:
    peanut = classify_ingredient("mantequilla de maní")
    pasta = classify_ingredient("whole wheat pasta")

    assert peanut is not None
    assert peanut.allergens == ("Maní",)
    assert pasta is not None
    assert pasta.allergens == ("Gluten",)


def test_unknown_ingredient_is_not_guessed() -> None:
    assert classify_ingredient("fruta inventada") is None


def test_classifier_does_not_match_an_allergen_word_inside_another_ingredient() -> None:
    assert classify_ingredient("eggplant") is None