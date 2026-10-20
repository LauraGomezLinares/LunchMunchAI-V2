"""Modelo de recetas guardadas por cada usuario."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


class FavoriteRecipe(SQLModel, table=True):
    """Receta completa guardada para consultarla sin regenerarla."""

    __tablename__ = "favoriterecipe"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "nombre",
            name="uq_favoriterecipe_usuario_nombre",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    usuario_id: UUID = Field(foreign_key="user.id", index=True)
    nombre: str = Field(max_length=200)
    receta: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    fecha_guardado: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
