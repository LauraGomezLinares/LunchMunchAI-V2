"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_origins(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [origin.strip() for origin in value.split(",") if origin.strip()]


class Settings(BaseSettings):
    """Settings required by the API and its authentication layer."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    firebase_credentials_json: str = Field(
        default="", validation_alias="FIREBASE_CREDENTIALS_JSON"
    )
    firebase_project_id: str = Field(default="", validation_alias="FIREBASE_PROJECT_ID")
    jwt_secret: str = Field(
        default="change-me-in-production", validation_alias="JWT_SECRET"
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES", gt=0
    )
    database_url: str = Field(
        default="sqlite:///./meal_muse.db", validation_alias="DATABASE_URL"
    )
    cors_origins: Annotated[list[str], BeforeValidator(_parse_origins)] = Field(
        default_factory=lambda: ["http://localhost:8081"],
        validation_alias="CORS_ORIGINS",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
