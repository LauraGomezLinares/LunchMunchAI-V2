"""Pruebas de calculo de ingredientes faltantes."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.security import get_current_user
from app.db.session import get_session
from app.main import app
from app.models.pantry import PantryItem
from app.models.user import User
from app.services.shopping_list import calcular_faltantes

test_engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
RECIPE_INGREDIENTS = [
    "500 g arroz",
    "1 unidad cebolla",
    "300 g chicken",
    "2 unidades garlic",
]


def _pantry_item(name: str, quantity: float, unit: str) -> PantryItem:
    return PantryItem(
        ingrediente=name,
        cantidad=quantity,
        unidad=unit,
        usuario_id=User(firebase_uid="shopping-user", email="shopping@example.com").id,
    )


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        user = User(firebase_uid="shopping-user", email="shopping@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)
        user_id = user.id

    def override_session() -> Generator[Session, None, None]:
        with Session(test_engine) as session:
            yield session

    def override_user() -> User:
        with Session(test_engine) as session:
            return session.get(User, user_id)  # type: ignore[return-value]

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    yield TestClient(app)
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(test_engine)


def test_empty_pantry_marks_every_recipe_ingredient_as_missing() -> None:
    missing = calcular_faltantes(RECIPE_INGREDIENTS, [])

    assert [item.nombre for item in missing] == [
        "arroz",
        "cebolla",
        "chicken",
        "garlic",
    ]
    assert missing[0].cantidad == 500
    assert missing[0].unidad == "g"


def test_complete_pantry_has_no_missing_ingredients() -> None:
    pantry = [
        _pantry_item("Arroz", 0.5, "kg"),
        _pantry_item("cebolla", 1, "unidad"),
        _pantry_item("Pollo", 300, "g"),
        _pantry_item("ajo", 2, "unidades"),
    ]

    assert calcular_faltantes(RECIPE_INGREDIENTS, pantry) == []


def test_partial_pantry_returns_missing_chicken_and_garlic_quantities() -> None:
    pantry = [
        _pantry_item("Arroz", 0.5, "kg"),
        _pantry_item("cebolla", 1, "unidad"),
    ]

    missing = calcular_faltantes(RECIPE_INGREDIENTS, pantry)

    assert [(item.nombre, item.cantidad, item.unidad) for item in missing] == [
        ("chicken", 300, "g"),
        ("garlic", 2, "unidades"),
    ]


def test_partial_quantity_returns_only_the_difference() -> None:
    missing = calcular_faltantes(
        ["500 g arroz"],
        [_pantry_item("arroz", 200, "g")],
    )

    assert [(item.cantidad, item.unidad) for item in missing] == [(300, "g")]
    assert missing[0].nota is None


def test_synonyms_tildes_and_case_are_normalized() -> None:
    missing = calcular_faltantes(
        ["300 g CHICKEN", "2 unidades GARLIC", "1 unidad lemon"],
        [
            _pantry_item("POLLO", 300, "g"),
            _pantry_item("AJO", 2, "unidades"),
            _pantry_item("LIM\u00d3N", 1, "unidad"),
        ],
    )

    assert missing == []


@pytest.mark.parametrize(
    ("recipe_amount", "recipe_unit", "pantry_amount", "pantry_unit"),
    [
        (1, "kg", 200, "g"),
        (500, "g", 0.2, "kg"),
    ],
)
def test_mass_units_convert_between_grams_and_kilograms(
    recipe_amount: float,
    recipe_unit: str,
    pantry_amount: float,
    pantry_unit: str,
) -> None:
    missing = calcular_faltantes(
        [f"{recipe_amount} {recipe_unit} arroz"],
        [_pantry_item("arroz", pantry_amount, pantry_unit)],
    )

    expected_amount = 0.8 if recipe_unit == "kg" else 300
    assert len(missing) == 1
    assert missing[0].cantidad == expected_amount
    assert missing[0].unidad == recipe_unit


def test_incomparable_units_include_verification_note() -> None:
    missing = calcular_faltantes(
        ["500 g arroz"],
        [_pantry_item("arroz", 2, "unidad")],
    )

    assert len(missing) == 1
    assert missing[0].nota == "verifica la cantidad"


def test_generate_recalculates_missing_ingredients_for_each_request(
    client: TestClient,
) -> None:
    with Session(test_engine) as session:
        user = session.exec(select(User)).one()
        session.add(PantryItem(ingrediente="arroz", cantidad=1, unidad="kg", usuario_id=user.id))
        session.commit()

    first = client.post("/api/v1/recipes/generate")
    assert first.status_code == 200
    assert "arroz" not in [
        item["nombre"] for item in first.json()["ingredientes_faltantes"]
    ]

    with Session(test_engine) as session:
        user = session.exec(select(User)).one()
        session.add(PantryItem(ingrediente="leche", cantidad=1, unidad="l", usuario_id=user.id))
        session.commit()

    second = client.post("/api/v1/recipes/generate")
    assert second.status_code == 200
    assert "leche" not in [
        item["nombre"] for item in second.json()["ingredientes_faltantes"]
    ]
