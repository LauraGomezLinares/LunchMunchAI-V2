"""Pruebas de vencimientos, visibilidad y prioridad segura de ingredientes."""

from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.security import get_current_user
from app.db.session import get_session
from app.main import app
from app.models.pantry import PantryItem
from app.models.user import User
from app.services.expiry import (
    clasificar_vencimiento,
    obtener_por_vencer,
    ordenar_por_vencimiento,
)

test_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        user = User(firebase_uid="expiry-a", email="expiry-a@example.com")
        other_user = User(firebase_uid="expiry-b", email="expiry-b@example.com")
        session.add_all([user, other_user])
        session.commit()
        session.refresh(user)
        session.refresh(other_user)
        active_user_id = [user.id]

    def override_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    def override_user() -> User:
        with Session(test_engine) as session:
            return session.get(User, active_user_id[0])  # type: ignore[return-value]

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    yield TestClient(app)
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(test_engine)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (0, ("por_vencer", 0)),
        (1, ("por_vencer", 1)),
        (-1, ("vencido", -1)),
        (3, ("por_vencer", 3)),
        (4, ("vigente", 4)),
    ],
)
def test_clasificar_vencimiento(offset: int, expected: tuple[str, int]) -> None:
    assert clasificar_vencimiento(date(2026, 1, 10) + timedelta(days=offset), date(2026, 1, 10)) == expected


def test_clasificar_fecha_ausente() -> None:
    assert clasificar_vencimiento(None, date(2026, 1, 10)) == ("sin_fecha", None)


def test_ordenar_por_vencimiento_deja_sin_fecha_al_final() -> None:
    user_id = User(firebase_uid="sort-test", email="sort@example.com").id
    items = [
        PantryItem(ingrediente="Sin fecha", cantidad=1, unidad="kg", usuario_id=user_id),
        PantryItem(
            ingrediente="Leche",
            cantidad=1,
            unidad="l",
            fecha_caducidad=date(2026, 1, 12),
            usuario_id=user_id,
        ),
        PantryItem(
            ingrediente="Arroz",
            cantidad=1,
            unidad="kg",
            fecha_caducidad=date(2026, 1, 11),
            usuario_id=user_id,
        ),
    ]

    assert [item.ingrediente for item in ordenar_por_vencimiento(items)] == [
        "Arroz",
        "Leche",
        "Sin fecha",
    ]
    assert [
        item.ingrediente for item in obtener_por_vencer(items, date(2026, 1, 10))
    ] == ["Leche", "Arroz"]


def test_pantry_response_has_expiry_fields_and_put_reorders_next_get(
    client: TestClient,
) -> None:
    today = date.today()
    later = client.post(
        "/api/v1/pantry/",
        json={
            "ingrediente": "Leche",
            "cantidad": 1,
            "unidad": "l",
            "fecha_caducidad": (today + timedelta(days=4)).isoformat(),
        },
    ).json()
    sooner = client.post(
        "/api/v1/pantry/",
        json={
            "ingrediente": "Espinaca",
            "cantidad": 1,
            "unidad": "kg",
            "fecha_caducidad": (today + timedelta(days=2)).isoformat(),
        },
    ).json()
    assert later["estado_vencimiento"] == "vigente"
    assert later["dias_para_vencer"] == 4
    assert sooner["estado_vencimiento"] == "por_vencer"
    assert sooner["dias_para_vencer"] == 2

    updated = client.put(
        f"/api/v1/pantry/{later['id']}",
        json={"fecha_caducidad": (today + timedelta(days=1)).isoformat()},
    )
    assert updated.status_code == 200
    assert updated.json()["dias_para_vencer"] == 1
    assert [item["ingrediente"] for item in client.get("/api/v1/pantry/").json()] == [
        "Leche",
        "Espinaca",
    ]


def test_expiring_summary_counts_upcoming_and_expired_items(
    client: TestClient,
) -> None:
    today = date.today()
    with Session(test_engine) as session:
        user = session.exec(select(User)).first()
        assert user is not None
        session.add_all(
            [
                PantryItem(
                    ingrediente="Hoy",
                    cantidad=1,
                    unidad="kg",
                    fecha_caducidad=today,
                    usuario_id=user.id,
                ),
                PantryItem(
                    ingrediente="Ayer",
                    cantidad=1,
                    unidad="kg",
                    fecha_caducidad=today - timedelta(days=1),
                    usuario_id=user.id,
                ),
                PantryItem(
                    ingrediente="Lejano",
                    cantidad=1,
                    unidad="kg",
                    fecha_caducidad=today + timedelta(days=4),
                    usuario_id=user.id,
                ),
            ]
        )
        session.commit()

    assert client.get("/api/v1/pantry/expiring-summary").json() == {
        "por_vencer": 1,
        "vencidos": 1,
    }


def test_expiry_summary_and_pantry_are_scoped_to_authenticated_user(
    client: TestClient,
) -> None:
    with Session(test_engine) as session:
        user_a, user_b = session.exec(select(User).order_by(User.email)).all()
        session.add_all(
            [
                PantryItem(
                    ingrediente="De A",
                    cantidad=1,
                    unidad="kg",
                    fecha_caducidad=date.today(),
                    usuario_id=user_a.id,
                ),
                PantryItem(
                    ingrediente="De B",
                    cantidad=1,
                    unidad="kg",
                    fecha_caducidad=date.today(),
                    usuario_id=user_b.id,
                ),
            ]
        )
        session.commit()
        user_b_id = user_b.id

    original_user_dependency = app.dependency_overrides[get_current_user]

    def override_other_user() -> User:
        with Session(test_engine) as session:
            return session.get(User, user_b_id)  # type: ignore[return-value]

    app.dependency_overrides[get_current_user] = override_other_user
    try:
        assert [item["ingrediente"] for item in client.get("/api/v1/pantry/").json()] == [
            "De B"
        ]
        assert client.get("/api/v1/pantry/expiring-summary").json() == {
            "por_vencer": 1,
            "vencidos": 0,
        }
    finally:
        app.dependency_overrides[get_current_user] = original_user_dependency


def test_expiring_ingredients_are_prioritized_when_compatible(
    client: TestClient,
) -> None:
    today = date.today()
    client.post(
        "/api/v1/pantry/",
        json={
            "ingrediente": "Leche",
            "cantidad": 1,
            "unidad": "l",
            "fecha_caducidad": (today + timedelta(days=1)).isoformat(),
        },
    )
    client.post(
        "/api/v1/pantry/",
        json={
            "ingrediente": "Espinaca",
            "cantidad": 1,
            "unidad": "kg",
            "fecha_caducidad": (today + timedelta(days=2)).isoformat(),
        },
    )

    response = client.post("/api/v1/recipes/generate")

    assert response.status_code == 200
    ingredients = response.json()["ingredientes"]
    assert "leche" in ingredients
    assert "espinaca" in ingredients


def test_expiry_priority_never_bypasses_allergen_filter(
    client: TestClient,
) -> None:
    today = date.today()
    with Session(test_engine) as session:
        user = session.exec(select(User)).first()
        assert user is not None
        user.alergias = ["Lácteos"]
        session.add(user)
        session.add(
            PantryItem(
                ingrediente="Leche",
                cantidad=1,
                unidad="l",
                fecha_caducidad=today + timedelta(days=1),
                usuario_id=user.id,
            )
        )
        session.add(
            PantryItem(
                ingrediente="Espinaca",
                cantidad=1,
                unidad="kg",
                fecha_caducidad=today + timedelta(days=2),
                usuario_id=user.id,
            )
        )
        session.commit()

    for _ in range(20):
        response = client.post("/api/v1/recipes/generate")
        assert response.status_code == 200
        assert "leche" not in response.json()["ingredientes"]
