"""taxonomia de ingredientes locales a pequeña escala para estandarizacion y clasificacion"""

import unicodedata
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IngredientInfo:
    """
    record de clasificacion local para un concepto de comida normalizado
    `canonical` es la identidad estable usada para comparar inventario con recetas;
    `category`es un grupo de comida grande;
    `aliases` son nombres en ingles/español aceptables;
    `allergens` lista etiquetas de perfil conocidas asociadas con los items; 
    este record es una ayuda, no una ontologia de comida completa
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
    IngredientInfo("pollo", "proteina", ("pollo", "chicken")),
    IngredientInfo("agua", "liquido", ("agua", "water")),
)


def normalize_ingredient(value: str) -> str:
    """normaliza una frase de ingrediente para q coincida sin acentos ni signos de puntuacion"""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(
        character if character.isalnum() else " "
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.split())


def classify_ingredient(value: str) -> IngredientInfo | None:
    """
    resuelve una frase de ingredientes conocidos sin adivinar nombres desconocidos
    coincidencia de aliases usa palabras completas, entonces `egg` no clasifica como `eggplant`
    si los aliases se superponen la coincidencia de alias mas larga gana (Por ejemplo, un nombre compuesto más específico 
    prevalece sobre una de sus palabras componentes más cortas.)
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