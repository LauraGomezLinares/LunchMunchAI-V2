"""Integration tests for Authentication API endpoints with SQLite in-memory database.

Architecture notes:
- Validates the end-to-end HTTP request/response contract across Router -> Schemas -> Services -> SQLite (StaticPool).
- Verifies JSON payloads, HTTP status codes, security boundaries, and local persistence idempotency.
"""

from typing import Any, Callable

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.services import auth_service


def test_register_new_user_success(client: TestClient) -> None:
    """Validate POST /api/v1/auth/register creates user and returns JWT token."""
    response = client.post("/api/v1/auth/register", json={"id_token": "valid-token"})
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "tester@mealmuse.com"
    assert data["user"]["nombre"] == "MealMuse Tester"


def test_register_with_custom_name_override(client: TestClient) -> None:
    """Validate that explicit nombre in register payload overrides Firebase claims name."""
    response = client.post(
        "/api/v1/auth/register",
        json={"id_token": "valid-token", "nombre": "Nombre Personalizado"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["nombre"] == "Nombre Personalizado"


def test_register_invalid_email_claim_fails_422(
    client: TestClient,
    mock_firebase: Callable[[dict[str, Any] | None], dict[str, Any]],
) -> None:
    """Validate that invalid email in Firebase token triggers HTTP 422."""
    mock_firebase({"uid": "bad-email-uid", "email": "invalid-email-address"})
    response = client.post("/api/v1/auth/register", json={"id_token": "valid-token"})
    assert response.status_code == 422
    assert "El correo de Firebase no tiene un formato válido." in response.json()["detail"]


def test_register_duplicate_email_conflict_fails_409(
    client: TestClient,
    mock_firebase: Callable[[dict[str, Any] | None], dict[str, Any]],
) -> None:
    """Validate registering with an email already belonging to another account returns HTTP 409."""
    # Primer registro exitoso con UID 1
    mock_firebase({"uid": "first-uid", "email": "shared@mealmuse.com"})
    res1 = client.post("/api/v1/auth/register", json={"id_token": "token-1"})
    assert res1.status_code == 201

    # Segundo registro con UID 2 pero mismo email -> Conflicto 409
    mock_firebase({"uid": "second-uid", "email": "shared@mealmuse.com"})
    res2 = client.post("/api/v1/auth/register", json={"id_token": "token-2"})
    assert res2.status_code == 409
    assert "El correo ya está registrado con otra cuenta." in res2.json()["detail"]


def test_login_success(client: TestClient) -> None:
    """Validate POST /api/v1/auth/login authenticates and synchronizes profile."""
    response = client.post("/api/v1/auth/login", json={"id_token": "valid-token"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "tester@mealmuse.com"


def test_firebase_login_success(client: TestClient) -> None:
    """Validate POST /api/v1/auth/firebase-login returns signed API session token."""
    response = client.post(
        "/api/v1/auth/firebase-login", json={"id_token": "valid-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_auth_endpoints_invalid_firebase_token_fails_401(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validate that invalid Firebase token verification raises HTTP 401."""
    def _reject(_: str) -> dict[str, Any]:
        raise HTTPException(
            status_code=401, detail="El token de Firebase no es válido o ha expirado."
        )

    monkeypatch.setattr(auth_service, "verify_firebase_token", _reject)

    response = client.post("/api/v1/auth/login", json={"id_token": "bad-token"})
    assert response.status_code == 401
    assert "El token de Firebase no es válido o ha expirado." in response.json()["detail"]


def test_me_authenticated_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Validate GET /api/v1/auth/me returns current authenticated user profile."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "tester@mealmuse.com"
    assert data["nombre"] == "MealMuse Tester"
    assert "id" in data


def test_me_without_authorization_header_fails_401(client: TestClient) -> None:
    """Validate GET /api/v1/auth/me without header returns HTTP 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "Se requiere un token Bearer." in response.json()["detail"]


def test_me_with_invalid_bearer_token_fails_401(client: TestClient) -> None:
    """Validate GET /api/v1/auth/me with bogus token returns HTTP 401."""
    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"}
    )
    assert response.status_code == 401


def test_logout_success(client: TestClient) -> None:
    """Validate POST /api/v1/auth/logout returns HTTP 204 No Content."""
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert response.text == ""
