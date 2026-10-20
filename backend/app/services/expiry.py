"""Clasificacion y orden de fechas de caducidad de la despensa."""

from datetime import date
from typing import Iterable

from app.models.pantry import PantryItem

EXPIRY_WARNING_DAYS = 3


def clasificar_vencimiento(
    fecha_caducidad: date | None, hoy: date | None = None
) -> tuple[str, int | None]:
    """Devuelve el estado y los dias restantes antes de la caducidad."""
    if fecha_caducidad is None:
        return "sin_fecha", None

    dias_para_vencer = (fecha_caducidad - (hoy or date.today())).days
    if dias_para_vencer < 0:
        return "vencido", dias_para_vencer
    if dias_para_vencer <= EXPIRY_WARNING_DAYS:
        return "por_vencer", dias_para_vencer
    return "vigente", dias_para_vencer


def ordenar_por_vencimiento(items: Iterable[PantryItem]) -> list[PantryItem]:
    """Ordena las fechas mas cercanas primero y deja las fechas vacias al final."""
    return sorted(
        items,
        key=lambda item: (
            item.fecha_caducidad is None,
            item.fecha_caducidad or date.max,
        ),
    )


def obtener_por_vencer(
    items: Iterable[PantryItem], hoy: date | None = None
) -> list[PantryItem]:
    """Devuelve solo los ingredientes dentro del periodo de aviso."""
    return [
        item
        for item in items
        if clasificar_vencimiento(item.fecha_caducidad, hoy)[0] == "por_vencer"
    ]
