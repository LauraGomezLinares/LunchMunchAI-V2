"""schemas de request y rpta de perfil de usuario."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """campos compartidor por schemas del perfil de usuario """

    nombre: str = Field(default="", max_length=120)
    email: EmailStr
    alergias: dict[str, Any] | list[Any] | None = None
    objetivos_nutricionales: str | None = Field(default=None, max_length=500)


class UserRead(UserBase):
    """representacion publica de un usuario local"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """campos editables del perfil para futuros endpoints del perfil"""

    nombre: str | None = Field(default=None, max_length=120)
    alergias: dict[str, Any] | list[Any] | None = None
    objetivos_nutricionales: str | None = Field(default=None, max_length=500)
