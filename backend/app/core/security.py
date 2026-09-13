"""Firebase and application-token security dependencies."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, credentials
from jose import JWTError, jwt
from sqlmodel import Session

from app.core.config import settings
from app.db.session import get_session
from app.models.user import User

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def _firebase_app() -> firebase_admin.App:
    """Initialize Firebase once, using inline JSON credentials when configured."""
    if firebase_admin._apps:
        return firebase_admin.get_app()
    if not settings.firebase_credentials_json:
        raise RuntimeError("Firebase credentials are not configured")
    try:
        credential_data = json.loads(settings.firebase_credentials_json)
        credential = credentials.Certificate(credential_data)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.error("Invalid Firebase credentials configuration")
        raise RuntimeError("Invalid Firebase credentials configuration") from exc
    options = (
        {"projectId": settings.firebase_project_id}
        if settings.firebase_project_id
        else None
    )
    return firebase_admin.initialize_app(credential, options)


def verify_firebase_token(id_token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and return its decoded claims."""
    try:
        _firebase_app()
        return auth.verify_id_token(id_token, check_revoked=True)
    except (firebase_admin.exceptions.FirebaseError, ValueError, RuntimeError) as exc:
        logger.warning("Firebase token verification failed: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Firebase no es válido o ha expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    """Create a short-lived signed session token for the API."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso no es válido o ha expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials_data: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """Resolve the current local user from an API JWT or Firebase ID token."""
    from app.services.auth_service import get_user_by_firebase_uid

    if credentials_data is None:
        raise HTTPException(
            status_code=401,
            detail="Se requiere un token Bearer.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials_data.credentials
    try:
        payload = _decode_access_token(token)
        firebase_uid = payload.get("sub")
        if not firebase_uid:
            raise JWTError("Missing subject")
        user = get_user_by_firebase_uid(session, firebase_uid)
    except HTTPException:
        raise
    except Exception:
        decoded = verify_firebase_token(token)
        firebase_uid = decoded.get("uid")
        user = get_user_by_firebase_uid(session, firebase_uid) if firebase_uid else None
    if not user:
        raise HTTPException(
            status_code=401,
            detail="El usuario autenticado no existe.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
