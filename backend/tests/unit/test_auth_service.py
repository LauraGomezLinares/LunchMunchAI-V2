"""Unit tests for authentication service logic with pure mocks."""

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.user import User
from app.services import auth_service


# En `test_auth_service.py` evaluamos las reglas de negocio de sincronización entre
# Firebase claims y el perfil local de la base de datos sin depender de conexiones reales.
# Usamos `MagicMock` para la sesión de base de datos y `mocker` para las utilidades de Firebase/JWT.


def test_get_user_by_email_normalizes_to_lowercase() -> None:
    """Validate that get_user_by_email queries with normalized lowercase email."""
    mock_session = MagicMock()
    mock_session.exec.return_value.first.return_value = User(
        email="test@mealmuse.com", firebase_uid="fb-1"
    )

    user = auth_service.get_user_by_email(mock_session, "TEST@MEALMUSE.COM")

    mock_session.exec.assert_called_once()
    assert user is not None
    assert user.email == "test@mealmuse.com"


def test_get_user_by_firebase_uid() -> None:
    """Validate that get_user_by_firebase_uid queries by subject UID."""
    mock_session = MagicMock()
    mock_session.exec.return_value.first.return_value = User(
        email="test@mealmuse.com", firebase_uid="fb-uid-100"
    )

    user = auth_service.get_user_by_firebase_uid(mock_session, "fb-uid-100")

    mock_session.exec.assert_called_once()
    assert user is not None
    assert user.firebase_uid == "fb-uid-100"


def test_create_user_from_firebase_new_user_success(mocker: Any) -> None:
    """Validate creating and persisting a brand new user from trusted Firebase claims."""
    mock_session = MagicMock()
    # No existe usuario previo por UID ni por Email
    mocker.patch("app.services.auth_service.get_user_by_firebase_uid", return_value=None)
    mocker.patch("app.services.auth_service.get_user_by_email", return_value=None)

    claims = {
        "uid": "fb-new-user",
        "email": "NEWUSER@MEALMUSE.COM",
        "name": "New User Name",
    }

    user = auth_service.create_user_from_firebase(mock_session, claims)

    # Verifica que el correo se haya normalizado a minúsculas
    assert user.email == "newuser@mealmuse.com"
    assert user.firebase_uid == "fb-new-user"
    assert user.nombre == "New User Name"
    mock_session.add.assert_called_once_with(user)
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(user)


def test_create_user_from_firebase_existing_user_update(mocker: Any) -> None:
    """Validate updating profile for an already synchronized user."""
    existing_user_id = uuid4()
    existing_user = User(
        id=existing_user_id,
        firebase_uid="fb-existing",
        email="old@mealmuse.com",
        nombre="Old Name",
    )
    mock_session = MagicMock()

    mocker.patch(
        "app.services.auth_service.get_user_by_firebase_uid",
        return_value=existing_user,
    )
    mocker.patch(
        "app.services.auth_service.get_user_by_email",
        return_value=existing_user,
    )

    claims = {
        "uid": "fb-existing",
        "email": "newemail@mealmuse.com",
        "name": "Updated Name",
    }

    updated_user = auth_service.create_user_from_firebase(
        mock_session, claims, nombre="Explicit Name"
    )

    assert updated_user.email == "newemail@mealmuse.com"
    assert updated_user.nombre == "Explicit Name"
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(existing_user)


def test_create_user_from_firebase_missing_claims_raises_401() -> None:
    """Validate that missing UID or Email in claims raises HTTPException 401."""
    mock_session = MagicMock()

    # Falta 'email'
    with pytest.raises(HTTPException) as exc_info_1:
        auth_service.create_user_from_firebase(mock_session, {"uid": "user-123"})
    assert exc_info_1.value.status_code == 401
    assert "El token no contiene una identidad válida." in exc_info_1.value.detail

    # Falta 'uid' / 'sub'
    with pytest.raises(HTTPException) as exc_info_2:
        auth_service.create_user_from_firebase(
            mock_session, {"email": "user@mealmuse.com"}
        )
    assert exc_info_2.value.status_code == 401
    assert "El token no contiene una identidad válida." in exc_info_2.value.detail


def test_create_user_from_firebase_invalid_email_format_raises_422() -> None:
    """Validate that invalid email format in claims raises HTTPException 422."""
    mock_session = MagicMock()
    claims = {"uid": "fb-bad-email", "email": "invalid-not-an-email"}

    with pytest.raises(HTTPException) as exc_info:
        auth_service.create_user_from_firebase(mock_session, claims)

    assert exc_info.value.status_code == 422
    assert "El correo de Firebase no tiene un formato válido." in exc_info.value.detail


def test_create_user_from_firebase_duplicate_email_conflict_raises_409(
    mocker: Any,
) -> None:
    """Validate that registering with an email already taken by another account raises 409."""
    mock_session = MagicMock()
    other_user = User(
        id=uuid4(),
        firebase_uid="different-uid",
        email="taken@mealmuse.com",
        nombre="Original Owner",
    )

    # Búsqueda por UID no encuentra nada (es nuevo), pero búsqueda por Email encuentra al usuario previo
    mocker.patch(
        "app.services.auth_service.get_user_by_firebase_uid", return_value=None
    )
    mocker.patch(
        "app.services.auth_service.get_user_by_email", return_value=other_user
    )

    claims = {"uid": "new-attacker-uid", "email": "taken@mealmuse.com"}

    with pytest.raises(HTTPException) as exc_info:
        auth_service.create_user_from_firebase(mock_session, claims)

    assert exc_info.value.status_code == 409
    assert "El correo ya está registrado con otra cuenta." in exc_info.value.detail


def test_create_access_token_delegates_to_security(mocker: Any) -> None:
    """Validate create_access_token delegates to security module with user claims."""
    mock_security_create = mocker.patch(
        "app.services.auth_service._create_access_token",
        return_value="mocked.jwt.token",
    )
    user = User(firebase_uid="uid-abc", email="user@mealmuse.com")

    token = auth_service.create_access_token(user)

    mock_security_create.assert_called_once_with(
        "uid-abc", {"email": "user@mealmuse.com"}
    )
    assert token == "mocked.jwt.token"


def test_register_user_orchestration(mocker: Any) -> None:
    """Validate register_user coordinates token verification and profile creation."""
    mock_session = MagicMock()
    mock_user = User(firebase_uid="uid-reg", email="reg@mealmuse.com")

    mocker.patch(
        "app.services.auth_service.verify_firebase_token",
        return_value={"uid": "uid-reg", "email": "reg@mealmuse.com"},
    )
    mock_create = mocker.patch(
        "app.services.auth_service.create_user_from_firebase",
        return_value=mock_user,
    )

    result = auth_service.register_user(mock_session, "raw-id-token", nombre="Reg Name")

    mock_create.assert_called_once_with(
        mock_session, {"uid": "uid-reg", "email": "reg@mealmuse.com"}, "Reg Name"
    )
    assert result == mock_user


def test_authenticate_user_delegation(mocker: Any) -> None:
    """Validate authenticate_user delegates to register_user."""
    mock_session = MagicMock()
    mock_user = User(firebase_uid="uid-auth", email="auth@mealmuse.com")
    mock_register = mocker.patch(
        "app.services.auth_service.register_user",
        return_value=mock_user,
    )

    result = auth_service.authenticate_user(mock_session, "raw-id-token")

    mock_register.assert_called_once_with(mock_session, "raw-id-token")
    assert result == mock_user


def test_revoke_firebase_token_success(mocker: Any) -> None:
    """Validate revoking Firebase session calls Firebase Admin SDK with UID."""
    mocker.patch(
        "app.services.auth_service.verify_firebase_token",
        return_value={"uid": "uid-to-revoke"},
    )
    mock_revoke = mocker.patch("firebase_admin.auth.revoke_refresh_tokens")

    auth_service.revoke_firebase_token("valid-id-token")

    mock_revoke.assert_called_once_with("uid-to-revoke")


def test_revoke_firebase_token_failure_raises_401(mocker: Any) -> None:
    """Validate that failures during Firebase token revocation raise HTTPException 401."""
    mocker.patch(
        "app.services.auth_service.verify_firebase_token",
        return_value={"uid": "uid-to-revoke"},
    )
    mocker.patch(
        "firebase_admin.auth.revoke_refresh_tokens",
        side_effect=ValueError("Revocation failed"),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_service.revoke_firebase_token("valid-id-token")

    assert exc_info.value.status_code == 401
    assert "No se pudo cerrar la sesión de Firebase." in exc_info.value.detail
