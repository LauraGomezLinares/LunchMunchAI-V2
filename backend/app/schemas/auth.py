"""Authentication request and response schemas."""

from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class UserRegister(BaseModel):
    """Firebase registration payload; passwords never reach this API."""

    id_token: str = Field(
        min_length=1, description="Firebase ID token obtained by the mobile client"
    )
    nombre: str | None = Field(default=None, max_length=120)


class UserLogin(BaseModel):
    """Firebase login payload."""

    id_token: str = Field(
        min_length=1, description="Firebase ID token obtained by the mobile client"
    )


class FirebaseLoginRequest(UserLogin):
    """Explicit Firebase login request used by `/firebase-login`."""


class Token(BaseModel):
    """Signed API session token and synchronized profile."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
