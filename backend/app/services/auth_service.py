"""Authentication orchestration and Firebase-to-local user synchronization."""

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from firebase_admin import auth
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlmodel import Session, select

from app.core.security import create_access_token as _create_access_token
from app.core.security import verify_firebase_token as _verify_firebase_token
from app.models.user import User


def get_user_by_email(session: Session, email: str) -> User | None:
    """Find a local user by normalized email."""
    return session.exec(select(User).where(User.email == email.lower())).first()


def get_user_by_firebase_uid(session: Session, firebase_uid: str) -> User | None:
    """Find a local user by Firebase subject."""
    return session.exec(select(User).where(User.firebase_uid == firebase_uid)).first()


def verify_firebase_token(id_token: str) -> dict[str, Any]:
    """Verify an ID token through Firebase Admin SDK."""
    return _verify_firebase_token(id_token)


def create_user_from_firebase(
    session: Session,
    claims: dict[str, Any],
    nombre: str | None = None,
) -> User:
    """Create or update a local profile from trusted Firebase claims."""
    firebase_uid = claims.get("uid") or claims.get("sub")
    email = claims.get("email")
    if not firebase_uid or not email:
        raise HTTPException(
            status_code=401, detail="El token no contiene una identidad válida."
        )
    try:
        normalized_email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail="El correo de Firebase no tiene un formato válido."
        ) from exc
    user = get_user_by_firebase_uid(session, str(firebase_uid))
    email_owner = get_user_by_email(session, normalized_email)
    if email_owner and (not user or email_owner.id != user.id):
        raise HTTPException(
            status_code=409, detail="El correo ya está registrado con otra cuenta."
        )
    if user is None:
        user = User(
            firebase_uid=str(firebase_uid),
            email=normalized_email,
            nombre=nombre or claims.get("name", ""),
        )
        session.add(user)
    else:
        user.email = normalized_email
        if nombre is not None:
            user.nombre = nombre
        elif not user.nombre:
            user.nombre = claims.get("name", "")
        user.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(user)
    return user


def create_access_token(user: User) -> str:
    """Create an API token linked to a synchronized Firebase user."""
    return _create_access_token(str(user.firebase_uid), {"email": user.email})


def register_user(session: Session, id_token: str, nombre: str | None = None) -> User:
    """Register through Firebase and synchronize the local profile."""
    return create_user_from_firebase(session, verify_firebase_token(id_token), nombre)


def authenticate_user(session: Session, id_token: str) -> User:
    """Authenticate through Firebase and synchronize the local profile."""
    return register_user(session, id_token)


def revoke_firebase_token(id_token: str) -> None:
    """Revoke a Firebase refresh session when a raw Firebase token is supplied."""
    claims = verify_firebase_token(id_token)
    try:
        auth.revoke_refresh_tokens(claims["uid"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=401, detail="No se pudo cerrar la sesión de Firebase."
        ) from exc
