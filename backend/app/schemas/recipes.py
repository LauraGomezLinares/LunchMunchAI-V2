"""solicitud de generacion de recetas y contrato de rpta estricta."""

from typing import Literal

from pydantic import BaseModel, Field


class RecipeGenerateRequest(BaseModel):
    """titulo opcional para omitir cuando el cliente quiera otra sugerencia"""

    excluir_receta: str | None = Field(default=None, min_length=1, max_length=200)


class Nutricion(BaseModel):
    """Valores nutricionales aproximados por porcion."""

    calorias_kcal: float | None = Field(default=None, ge=0)
    proteinas_g: float | None = Field(default=None, ge=0)
    carbohidratos_g: float | None = Field(default=None, ge=0)
    grasas_g: float | None = Field(default=None, ge=0)


class RecipeRead(BaseModel):
    """rpta json estable compartida por proveedores locales, simulados y externos."""

    nombre: str
    tiempo_estimado_minutos: int = Field(ge=1)
    porciones: int = Field(ge=1)
    calorias: int = Field(ge=0)
    nutricion: Nutricion | None = None
    ingredientes: list[str]
    pasos: list[str]
    apto_para_alergias: Literal[True]