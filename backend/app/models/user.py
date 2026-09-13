"""Local user persistence model."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON, String
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """Application profile synchronized from Firebase Authentication."""

    __tablename__ = "user"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    firebase_uid: str = Field(index=True, unique=True, max_length=128)
    nombre: str = Field(default="", max_length=120)
    email: str = Field(
        sa_column=Column(String(320), unique=True, index=True, nullable=False)
    )
    hashed_password: str | None = Field(default=None, nullable=True)
    alergias: dict[str, Any] | list[Any] | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    objetivos_nutricionales: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )
