"""Unit tests for core security and token handling utilities.

Architecture notes:
- Uses pytest-mock and unittest.mock to completely isolate external dependencies
  (Google Firebase Admin SDK and database sessions).
- Validates cryptographic JWT encoding, expiration enforcement, tampering detection,
  and authentication fallback resolution deterministically.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.config import settings
from app.core.security import (
    _decode_access_token,
    create_access_token,
    get_current_user,
    verify_firebase_token,
)
from app.models.user import User


def test_create_access_token_structure() -> None:
    """Validate that create_access_token encodes expected subject, claims, and expiration."""
    subject = "user-firebase-123"
    custom_claims = {"email": "tester@mealmuse.com", "role": "admin"}

    token = create_access_token(subject=subject, claims=custom_claims)

    decoded = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    assert decoded["sub"] == subject
    assert decoded["email"] == "tester@mealmuse.com"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded


def test_decode_access_token_success() -> None:
    """Validate successful decoding of an active JWT access token."""
    subject = "user-valid-jwt"
    token = create_access_token(subject=subject, claims={"email": "valid@mealmuse.com"})

    payload = _decode_access_token(token)

    assert payload["sub"] == subject
    assert payload["email"] == "valid@mealmuse.com"


def test_decode_access_token_expired() -> None:
    """Validate that an expired JWT raises HTTPException 401."""
    past_time = datetime.now(timezone.utc) - timedelta(hours=2)
    expired_payload: dict[str, Any] = {
        "sub": "user-expired",
        "iat": past_time - timedelta(minutes=60),
        "exp": past_time,
    }
    expired_token = jwt.encode(
        expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    with pytest.raises(HTTPException) as exc_info:
        _decode_access_token(expired_token)

    assert exc_info.value.status_code == 401
    assert "El token de acceso no es válido o ha expirado." in exc_info.value.detail


def test_decode_access_token_invalid_signature() -> None:
    """Validate that a JWT signed with an untrusted secret raises HTTPException 401."""
    fake_token = jwt.encode(
        {"sub": "intruder", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "wrong-secret-key",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc_info:
        _decode_access_token(fake_token)

    assert exc_info.value.status_code == 401
    assert "El token de acceso no es válido o ha expirado." in exc_info.value.detail


def test_verify_firebase_token_success(mocker: Any) -> None:
    """Validate verify_firebase_token decoding with mocked Firebase Admin SDK."""
    mocker.patch("app.core.security._firebase_app", return_value=MagicMock())
    mock_verify = mocker.patch(
        "firebase_admin.auth.verify_id_token",
        return_value={"uid": "fb-uid-999", "email": "firebase@mealmuse.com"},
    )

    claims = verify_firebase_token("fake-firebase-id-token")

    mock_verify.assert_called_once_with("fake-firebase-id-token", check_revoked=True)
    assert claims["uid"] == "fb-uid-999"
    assert claims["email"] == "firebase@mealmuse.com"


def test_verify_firebase_token_invalid_raises_401(mocker: Any) -> None:
    """Validate that invalid Firebase token verification raises HTTPException 401."""
    mocker.patch("app.core.security._firebase_app", return_value=MagicMock())
    mocker.patch(
        "firebase_admin.auth.verify_id_token",
        side_effect=ValueError("Invalid Firebase ID token"),
    )

    with pytest.raises(HTTPException) as exc_info:
        verify_firebase_token("invalid-token")

    assert exc_info.value.status_code == 401
    assert "El token de Firebase no es válido o ha expirado." in exc_info.value.detail


def test_get_current_user_no_credentials_raises_401() -> None:
    """Validate that missing Bearer credentials raises HTTPException 401."""
    mock_session = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials_data=None, session=mock_session)

    assert exc_info.value.status_code == 401
    assert "Se requiere un token Bearer." in exc_info.value.detail


def test_get_current_user_valid_jwt(mocker: Any) -> None:
    """Validate resolving user from a valid local JWT without querying real DB."""
    mock_user = User(
        firebase_uid="uid-jwt-1", email="jwt@mealmuse.com", nombre="JWT User"
    )
    mock_session = MagicMock()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="valid.jwt.token"
    )

    mocker.patch(
        "app.core.security._decode_access_token", return_value={"sub": "uid-jwt-1"}
    )
    mocker.patch(
        "app.services.auth_service.get_user_by_firebase_uid", return_value=mock_user
    )

    user = get_current_user(credentials_data=credentials, session=mock_session)

    assert user.firebase_uid == "uid-jwt-1"
    assert user.email == "jwt@mealmuse.com"


def test_get_current_user_fallback_to_firebase_token(mocker: Any) -> None:
    """Validate fallback to Firebase token verification when local JWT decoding fails."""
    mock_user = User(
        firebase_uid="fb-uid-fallback",
        email="fb@mealmuse.com",
        nombre="Firebase User",
    )
    mock_session = MagicMock()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="raw.firebase.token"
    )

    mocker.patch(
        "app.core.security._decode_access_token",
        side_effect=HTTPException(status_code=401, detail="Not a local JWT"),
    )
    mocker.patch(
        "app.core.security.verify_firebase_token",
        return_value={"uid": "fb-uid-fallback", "email": "fb@mealmuse.com"},
    )
    mocker.patch(
        "app.services.auth_service.get_user_by_firebase_uid", return_value=mock_user
    )

    user = get_current_user(credentials_data=credentials, session=mock_session)

    assert user.firebase_uid == "fb-uid-fallback"
    assert user.email == "fb@mealmuse.com"


def test_get_current_user_not_found_raises_401(mocker: Any) -> None:
    """Validate that valid token for non-existent database user raises HTTPException 401."""
    mock_session = MagicMock()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="valid.jwt.token"
    )

    mocker.patch(
        "app.core.security._decode_access_token", return_value={"sub": "ghost-user-uid"}
    )
    mocker.patch(
        "app.services.auth_service.get_user_by_firebase_uid", return_value=None
    )

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials_data=credentials, session=mock_session)

    assert exc_info.value.status_code == 401
    assert "El usuario autenticado no existe." in exc_info.value.detail
