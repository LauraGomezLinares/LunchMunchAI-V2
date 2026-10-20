"""Esquemas de entrada y salida para recetas favoritas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.recipes import RecipeRead


class FavoriteCreate(RecipeRead):
    """El cliente envía el contrato completo de receta como cuerpo."""


class FavoriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    receta: RecipeRead
    fecha_guardado: datetime
