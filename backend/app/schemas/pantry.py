"""pantry schemas - validacion de entrada/salida"""

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

# ---------------------------------------------------------------------------
# Unidades de medida aceptadas por el sistema
# ---------------------------------------------------------------------------
# Masa / Peso
#   kg  -> kilogramos
#   g   -> gramos
#   mg  -> miligramos
#   lb  -> libras
#   oz  -> onzas
# Volumen
#   l   -> litros
#   ml  -> mililitros
#   taza -> taza (cup)
#   tbsp -> cucharada (tablespoon)
#   tsp  -> cucharadita (teaspoon)
# Cantidad / comodín
#   unidad -> pieza sin medida específica (huevo, aguacate, etc.)
#   piezas -> varias piezas
# ---------------------------------------------------------------------------
UnidadMedida = Literal[
    "kg",
    "g",
    "mg",
    "lb",
    "oz",
    "l",
    "ml",
    "unidad",
]


class PantryItemCreate(BaseModel):
    ingrediente: str = Field(min_length=1, max_length=120)
    cantidad: float = Field(gt=0)
    unidad: UnidadMedida
    fecha_caducidad: Optional[date] = None


class PantryItemUpdate(BaseModel):
    ingrediente: Optional[str] = Field(default=None, min_length=1, max_length=120)
    cantidad: Optional[float] = Field(default=None, gt=0)
    unidad: Optional[UnidadMedida] = None
    fecha_caducidad: Optional[date] = None


class PantryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingrediente: str
    cantidad: float
    unidad: str
    fecha_caducidad: Optional[date]
    created_at: datetime