"""Small local ingredient taxonomy for canonicalization and classification."""

import unicodedata
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IngredientInfo:
    """Local classification record for one normalized food concept.

    `canonical` is the stable identity used to compare inventory with recipes;
    `category` is a broad food group; `aliases` are accepted Spanish/English
    names; and `allergens` lists known profile labels associated with the item.
    This record is a lookup aid, not a complete food ontology.
    """

    canonical: str
    category: str
    aliases: tuple[str, ...]
    allergens: tuple[str, ...] = ()


INGREDIENTS = (
    IngredientInfo("arroz", "cereal", ("arroz", "rice")),
    IngredientInfo("tomate", "verdura", ("tomate", "tomates", "tomato", "tomatoes", "jitomate")),
    IngredientInfo("espinaca", "verdura", ("espinaca", "spinach")),
    IngredientInfo("cebolla", "verdura", ("cebolla", "onion")),
    IngredientInfo("zanahoria", "verdura", ("zanahoria", "carrot")),
    IngredientInfo("ajo", "verdura", ("ajo", "garlic")),
    IngredientInfo("pepino", "verdura", ("pepino", "cucumber")),
    IngredientInfo("papa", "tuberculo", ("papa", "patata", "potato", "potatoes")),
    IngredientInfo("pimiento", "verdura", ("pimiento", "morrón", "bell pepper", "capsicum")),
    IngredientInfo("limon", "fruta", ("limon", "lima", "lemon", "lime")),
    IngredientInfo("aceite de oliva", "grasa", ("aceite de oliva", "olive oil")),
    IngredientInfo("lentejas", "legumbre", ("lenteja", "lentejas", "lentil", "lentils")),
    IngredientInfo("garbanzos", "legumbre", ("garbanzo", "garbanzos", "chickpea", "chickpeas")),
    IngredientInfo("frijoles", "legumbre", ("frijol", "frijoles", "poroto", "porotos", "bean", "beans")),
    IngredientInfo("avena", "cereal", ("avena", "oat", "oats")),
    IngredientInfo("banana", "fruta", ("banana", "platano", "banano", "plantain")),
    IngredientInfo("canela", "especia", ("canela", "cinnamon")),
    IngredientInfo("maiz", "cereal", ("maiz", "elote", "corn")),
    IngredientInfo("quinoa", "cereal", ("quinoa", "quinua")),
    IngredientInfo("pasta de trigo", "cereal", ("pasta", "fideos", "noodles", "wheat pasta"), ("Gluten",)),
    IngredientInfo("pan de trigo", "cereal", ("pan", "bread", "wheat bread"), ("Gluten",)),
    IngredientInfo("huevo", "proteina", ("huevo", "huevos", "egg", "eggs"), ("Huevos",)),
    IngredientInfo("leche", "lacteo", ("leche", "milk", "cream"), ("Lácteos",)),
    IngredientInfo("queso", "lacteo", ("queso", "cheese"), ("Lácteos",)),
    IngredientInfo("yogur", "lacteo", ("yogur", "yogurt"), ("Lácteos",)),
    IngredientInfo("mani", "fruto seco", ("mani", "cacahuate", "peanut", "groundnut"), ("Maní",)),
    IngredientInfo("almendra", "fruto seco", ("almendra", "almendras", "almond", "almonds"), ("Frutos secos",)),
    IngredientInfo("nuez", "fruto seco", ("nuez", "nueces", "walnut", "walnuts"), ("Frutos secos",)),
    IngredientInfo("soya", "legumbre", ("soya", "soja", "soy", "soybean", "tofu"), ("Soya",)),
    IngredientInfo("salmon", "pescado", ("salmon", "salmon fillet"), ("Pescado",)),
    IngredientInfo("atun", "pescado", ("atun", "tuna"), ("Pescado",)),
    IngredientInfo("camaron", "marisco", ("camaron", "camarones", "shrimp", "prawn"), ("Mariscos",)),
    IngredientInfo("agua", "liquido", ("agua", "water")),
)


def normalize_ingredient(value: str) -> str:
    """Normalize an ingredient phrase for accent- and punctuation-free matching."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(
        character if character.isalnum() else " "
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.split())


def classify_ingredient(value: str) -> IngredientInfo | None:
    """Resolve a known ingredient phrase without guessing unknown names.

    Alias matching uses complete words, so `egg` does not classify `eggplant`.
    If aliases overlap, the longest matching alias wins (for example, a more
    specific compound name wins over one of its shorter component words).
    """
    normalized = normalize_ingredient(value)
    if not normalized:
        return None
    matches = []
    for info in INGREDIENTS:
        for alias in info.aliases:
            normalized_alias = normalize_ingredient(alias)
            if re.search(rf"(?<!\w){re.escape(normalized_alias)}(?!\w)", normalized):
                matches.append((normalized_alias, info))
    if not matches:
        return None
    return max(matches, key=lambda match: len(match[0]))[1]