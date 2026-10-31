"""Calculo sin estado de ingredientes y cantidades que faltan para una receta."""

import re
from collections.abc import Sequence

from app.models.pantry import PantryItem
from app.schemas.recipes import IngredienteFaltante
from app.services.ingredient_catalog import classify_ingredient, normalize_ingredient

_AMOUNT_PATTERN = re.compile(
    r"^\s*(?P<amount>\d+(?:[.,]\d+)?)\s+(?P<rest>.+?)\s*$",
    re.IGNORECASE,
)
_UNIT_ALIASES = {
    "unit": "unidad",
    "units": "unidad",
    "piece": "unidad",
    "pieces": "unidad",
    "unidad": "unidad",
    "unidades": "unidad",
    "pieza": "unidad",
    "piezas": "unidad",
    "cup": "cup",
    "cups": "cup",
    "taza": "cup",
    "tazas": "cup",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
}
_UNIT_FACTORS = {
    "g": ("masa", 1.0),
    "kg": ("masa", 1000.0),
    "mg": ("masa", 0.001),
    "lb": ("masa", 453.59237),
    "oz": ("masa", 28.349523125),
    "ml": ("volumen", 1.0),
    "l": ("volumen", 1000.0),
}
_VERIFY_QUANTITY_NOTE = "verifica la cantidad"


def _parse_ingredient(value: str) -> tuple[str, float | None, str | None]:
    """Lee cantidades iniciales sencillas, por ejemplo '500 g arroz'."""
    match = _AMOUNT_PATTERN.match(value)
    if not match:
        return value.strip(), None, None
    amount = float(match.group("amount").replace(",", "."))
    rest = match.group("rest").strip()
    parts = rest.split(maxsplit=1)
    first_word = normalize_ingredient(parts[0])
    known_units = {*_UNIT_ALIASES, *_UNIT_FACTORS}
    if first_word in known_units and len(parts) == 2:
        return parts[1].strip(), amount, first_word
    return rest, amount, None


def _canonical_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    normalized = normalize_ingredient(unit)
    return _UNIT_ALIASES.get(normalized, normalized)


def _to_base(amount: float, unit: str | None) -> tuple[str, float] | None:
    canonical = _canonical_unit(unit)
    if canonical is None:
        return None
    if canonical in _UNIT_FACTORS:
        dimension, factor = _UNIT_FACTORS[canonical]
        return dimension, amount * factor
    return canonical, amount


def _same_ingredient(left: str, right: str) -> bool:
    left_info = classify_ingredient(left)
    right_info = classify_ingredient(right)
    if left_info and right_info:
        return left_info.canonical == right_info.canonical
    return normalize_ingredient(left) == normalize_ingredient(right)


def calcular_faltantes(
    ingredientes_receta: Sequence[str], items_despensa: Sequence[PantryItem]
) -> list[IngredienteFaltante]:
    """Compara ingredientes y descuenta cantidades de unidades compatibles."""
    faltantes: list[IngredienteFaltante] = []
    for recipe_text in ingredientes_receta:
        nombre, cantidad, unidad = _parse_ingredient(recipe_text)
        matching_items = [
            item for item in items_despensa if _same_ingredient(nombre, item.ingrediente)
        ]
        if not matching_items:
            faltantes.append(
                IngredienteFaltante(
                    nombre=nombre,
                    cantidad=cantidad,
                    unidad=unidad,
                )
            )
            continue

        if cantidad is None:
            continue

        recipe_base = _to_base(cantidad, unidad)
        pantry_total = 0.0
        comparable = False
        incomparable = False
        if recipe_base is None:
            faltantes.append(
                IngredienteFaltante(
                    nombre=nombre,
                    cantidad=cantidad,
                    unidad=unidad,
                    nota=_VERIFY_QUANTITY_NOTE,
                )
            )
            continue

        recipe_dimension, _ = recipe_base
        for item in matching_items:
            pantry_base = _to_base(item.cantidad, item.unidad)
            if pantry_base is None or pantry_base[0] != recipe_dimension:
                incomparable = True
                continue
            comparable = True
            pantry_total += pantry_base[1]

        if not comparable:
            faltantes.append(
                IngredienteFaltante(
                    nombre=nombre,
                    cantidad=cantidad,
                    unidad=unidad,
                    nota=_VERIFY_QUANTITY_NOTE,
                )
            )
            continue

        missing_base = recipe_base[1] - pantry_total
        if missing_base > 0:
            factor = _UNIT_FACTORS.get(_canonical_unit(unidad) or "", ("", 1.0))[1]
            faltantes.append(
                IngredienteFaltante(
                    nombre=nombre,
                    cantidad=round(missing_base / factor, 6),
                    unidad=unidad,
                    nota=_VERIFY_QUANTITY_NOTE if incomparable else None,
                )
            )

    return faltantes
