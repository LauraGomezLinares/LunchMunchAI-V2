"""Recipe generation request and strict response contracts."""

from typing import Literal

from pydantic import BaseModel, Field


class RecipeGenerateRequest(BaseModel):
    excluir_receta: str | None = Field(default=None, min_length=1, max_length=200)


class RecipeRead(BaseModel):
    nombre: str
    tiempo_estimado_minutos: int = Field(ge=1)
    porciones: int = Field(ge=1)
    calorias: int = Field(ge=0)
    ingredientes: list[str]
    pasos: list[str]
    apto_para_alergias: Literal[True]