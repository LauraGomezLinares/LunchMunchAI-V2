"""endpoints auth HTTP"""

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.security import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import FirebaseLoginRequest, Token, UserLogin, UserRegister
from app.schemas.user import UserRead
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    register_user,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def _token_response(user: User) -> Token:
    return Token(
        access_token=create_access_token(user), user=UserRead.model_validate(user)
    )


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Token Firebase inválido"},
        409: {"description": "Correo duplicado"},
    },
)
def register(payload: UserRegister, session: Session = Depends(get_session)) -> Token:
    """registra usuario a firebase y se crea el perfil local correspondiente"""
    return _token_response(register_user(session, payload.id_token, payload.nombre))


@router.post(
    "/login",
    response_model=Token,
    responses={401: {"description": "Credenciales incorrectas"}},
)
def login(payload: UserLogin, session: Session = Depends(get_session)) -> Token:
    """auth con un token de id firebase"""
    return _token_response(authenticate_user(session, payload.id_token))


@router.post(
    "/firebase-login",
    response_model=Token,
    responses={401: {"description": "Token Firebase inválido"}},
)
def firebase_login(
    payload: FirebaseLoginRequest, session: Session = Depends(get_session)
) -> Token:
    """revisa firebase y retorna un token de sesion de api firmado"""
    return _token_response(authenticate_user(session, payload.id_token))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    """retorna el perfil local del usuario autentical"""
    return UserRead.model_validate(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> None:
    """termina la sesion local, cliente descarta el jwt de corta duracion"""
    return None
