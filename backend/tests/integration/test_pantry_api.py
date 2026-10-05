"""Integration tests for Pantry API endpoints with multi-user isolation."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token
from app.models.user import User


# EXPLICACIÓN ARQUITECTÓNICA (POR QUÉ Y CÓMO):
# En `test_pantry_api.py` evaluamos las operaciones CRUD del inventario y la seguridad multitenant.
# Verificamos que las consultas aíslen estrictamente los datos por `usuario_id` para que ningún
# usuario pueda acceder, alterar o eliminar registros pertenecientes a otro usuario.


def _create_secondary_user(db_session: Session) -> tuple[User, dict[str, str]]:
    """Helper to provision a second user in the test database with authorization headers."""
    user_b = User(
        firebase_uid="firebase-user-b-456",
        email="user_b@mealmuse.com",
        nombre="Usuario B",
    )
    db_session.add(user_b)
    db_session.commit()
    db_session.refresh(user_b)
    token = create_access_token(str(user_b.firebase_uid), {"email": user_b.email})
    headers = {"Authorization": f"Bearer {token}"}
    return user_b, headers


def test_create_pantry_item_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Validate POST /api/v1/pantry/ creates a new ingredient associated with the current user."""
    payload = {
        "ingrediente": "Tomates",
        "cantidad": 500.0,
        "unidad": "g",
        "fecha_caducidad": "2026-10-15",
    }
    response = client.post("/api/v1/pantry/", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["ingrediente"] == "Tomates"
    assert data["cantidad"] == 500.0
    assert data["unidad"] == "g"
    assert data["fecha_caducidad"] == "2026-10-15"
    assert "id" in data
    assert "created_at" in data


def test_create_pantry_item_invalid_quantity_fails_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Validate that creating an item with non-positive quantity triggers HTTP 422."""
    payload = {"ingrediente": "Sal", "cantidad": 0, "unidad": "g"}
    response = client.post("/api/v1/pantry/", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_create_pantry_item_unauthenticated_fails_401(client: TestClient) -> None:
    """Validate that unauthenticated requests to create item return HTTP 401."""
    payload = {"ingrediente": "Azúcar", "cantidad": 1.0, "unidad": "kg"}
    response = client.post("/api/v1/pantry/", json=payload)
    assert response.status_code == 401


def test_list_pantry_empty_initially(client: TestClient, auth_headers: dict[str, str]) -> None:
    """Validate GET /api/v1/pantry/ returns an empty list when no items exist."""
    response = client.get("/api/v1/pantry/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_pantry_ordered_by_expiration_nulls_last(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Validate GET /api/v1/pantry/ returns ingredients sorted by expiration date ascending with nulls last."""
    # Insertamos ítems en desorden temporal
    client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Leche", "cantidad": 1.0, "unidad": "L", "fecha_caducidad": "2026-10-25"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Sal marina", "cantidad": 500.0, "unidad": "g", "fecha_caducidad": None},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Yogur", "cantidad": 200.0, "unidad": "g", "fecha_caducidad": "2026-10-10"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/pantry/", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 3

    # Orden esperado: 2026-10-10 (Yogur) -> 2026-10-25 (Leche) -> None (Sal marina)
    assert items[0]["ingrediente"] == "Yogur"
    assert items[0]["fecha_caducidad"] == "2026-10-10"
    assert items[1]["ingrediente"] == "Leche"
    assert items[1]["fecha_caducidad"] == "2026-10-25"
    assert items[2]["ingrediente"] == "Sal marina"
    assert items[2]["fecha_caducidad"] is None


def test_update_pantry_item_partial_success(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Validate partial update with PUT /api/v1/pantry/{item_id}."""
    created = client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Huevos", "cantidad": 12.0, "unidad": "unidades"},
        headers=auth_headers,
    ).json()

    response = client.put(
        f"/api/v1/pantry/{created['id']}",
        json={"cantidad": 6.0},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["cantidad"] == 6.0
    assert data["ingrediente"] == "Huevos"
    assert data["unidad"] == "unidades"


def test_update_pantry_item_not_found_fails_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Validate updating non-existent item returns HTTP 404."""
    random_id = uuid4()
    response = client.put(
        f"/api/v1/pantry/{random_id}",
        json={"cantidad": 5.0},
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert "Ingrediente no encontrado" in response.json()["detail"]


def test_update_pantry_item_invalid_quantity_fails_422(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Validate that non-positive quantity on update fails with HTTP 422."""
    created = client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Harina", "cantidad": 1.0, "unidad": "kg"},
        headers=auth_headers,
    ).json()

    response = client.put(
        f"/api/v1/pantry/{created['id']}",
        json={"cantidad": -2.0},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_delete_pantry_item_success(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Validate DELETE /api/v1/pantry/{item_id} removes the ingredient."""
    created = client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Mantequilla", "cantidad": 250.0, "unidad": "g"},
        headers=auth_headers,
    ).json()

    delete_res = client.delete(
        f"/api/v1/pantry/{created['id']}", headers=auth_headers
    )
    assert delete_res.status_code == 204

    # Verificamos que ya no aparezca en el listado
    list_res = client.get("/api/v1/pantry/", headers=auth_headers)
    assert all(item["id"] != created["id"] for item in list_res.json())


def test_delete_pantry_item_not_found_fails_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Validate deleting non-existent item returns HTTP 404."""
    random_id = uuid4()
    response = client.delete(f"/api/v1/pantry/{random_id}", headers=auth_headers)
    assert response.status_code == 404
    assert "Ingrediente no encontrado" in response.json()["detail"]


def test_multitenant_isolation_list(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Validate that User B cannot see ingredients created by User A in list."""
    # Usuario A crea un ingrediente
    client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Trufas Negras", "cantidad": 50.0, "unidad": "g"},
        headers=auth_headers,
    )

    # Usuario B consulta su propia despensa
    _, headers_b = _create_secondary_user(db_session)
    response_b = client.get("/api/v1/pantry/", headers=headers_b)

    assert response_b.status_code == 200
    assert response_b.json() == []


def test_multitenant_isolation_update_forbidden_404(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Validate that User B cannot update an ingredient created by User A."""
    # Usuario A crea un ingrediente
    item_a = client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Azafrán", "cantidad": 10.0, "unidad": "g"},
        headers=auth_headers,
    ).json()

    # Usuario B intenta modificar el ingrediente de A
    _, headers_b = _create_secondary_user(db_session)
    response_b = client.put(
        f"/api/v1/pantry/{item_a['id']}",
        json={"cantidad": 999.0},
        headers=headers_b,
    )

    # Debe retornar 404 para no filtrar existencia de recursos ajenos
    assert response_b.status_code == 404
    assert "Ingrediente no encontrado" in response_b.json()["detail"]


def test_multitenant_isolation_delete_forbidden_404(
    client: TestClient,
    auth_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Validate that User B cannot delete an ingredient created by User A."""
    # Usuario A crea un ingrediente
    item_a = client.post(
        "/api/v1/pantry/",
        json={"ingrediente": "Caviar", "cantidad": 100.0, "unidad": "g"},
        headers=auth_headers,
    ).json()

    # Usuario B intenta borrar el ingrediente de A
    _, headers_b = _create_secondary_user(db_session)
    response_b = client.delete(
        f"/api/v1/pantry/{item_a['id']}", headers=headers_b
    )

    assert response_b.status_code == 404
    assert "Ingrediente no encontrado" in response_b.json()["detail"]

    # Verificamos que el ítem siga intacto para Usuario A
    list_a = client.get("/api/v1/pantry/", headers=auth_headers).json()
    assert any(item["id"] == item_a["id"] for item in list_a)
