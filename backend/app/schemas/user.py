"""User profile request and response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Fields shared by user profile schemas."""

    nombre: str = Field(default="", max_length=120)
    email: EmailStr
    alergias: dict[str, Any] | list[Any] | None = None
    objetivos_nutricionales: str | None = Field(default=None, max_length=500)


class UserRead(UserBase):
    """Public representation of a local user."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class UserUpdate(BaseModel):
    """Editable profile fields for future profile endpoints."""

    nombre: str | None = Field(default=None, max_length=120)
    alergias: dict[str, Any] | list[Any] | None = None
    objetivos_nutricionales: str | None = Field(default=None, max_length=500)
