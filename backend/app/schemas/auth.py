"""schema de requests y rptas de auth"""

from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class UserRegister(BaseModel):
    """payload de registro de firebase, contras nunca llegan a esta api."""

    id_token: str = Field(
        min_length=1, description="Firebase ID token obtained by the mobile client"
    )
    nombre: str | None = Field(default=None, max_length=120)


class UserLogin(BaseModel):
    """payload de logueo de firebase"""

    id_token: str = Field(
        min_length=1, description="Firebase ID token obtained by the mobile client"
    )


class FirebaseLoginRequest(UserLogin):
    """request de logueo de firebase explicita usada por `/firebase-login`"""


class Token(BaseModel):
    """token de sesion de api firmado perfil sincronizado"""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
