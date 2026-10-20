"""Esquemas de entrada y salida para recetas favoritas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recipes import RecipeRead


class FavoriteCreate(RecipeRead):
    """El cliente envía el contrato completo de receta como cuerpo."""

    nombre: str = Field(min_length=1, max_length=200)


class FavoriteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    receta: RecipeRead
    fecha_guardado: datetime
