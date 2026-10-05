"""Unit tests for Pydantic validation schemas (Auth, User, Pantry)."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.auth import FirebaseLoginRequest, Token, UserLogin, UserRegister
from app.schemas.pantry import PantryItemCreate, PantryItemRead, PantryItemUpdate
from app.schemas.user import UserBase, UserRead, UserUpdate


# En `test_schemas.py` evaluamos las restricciones, tipos e invariantes declaradas
# en los modelos de validación de Pydantic sin necesidad de inicializar bases de datos ni clientes HTTP.


def test_pantry_item_create_valid() -> None:
    """Validate creating a PantryItemCreate with valid fields."""
    payload = {
        "ingrediente": "Zanahorias",
        "cantidad": 500.0,
        "unidad": "g",
        "fecha_caducidad": "2026-11-20",
    }
    item = PantryItemCreate(**payload)
    assert item.ingrediente == "Zanahorias"
    assert item.cantidad == 500.0
    assert item.unidad == "g"
    assert item.fecha_caducidad == date(2026, 11, 20)


@pytest.mark.parametrize("invalid_qty", [0, -1, -0.01])
def test_pantry_item_create_zero_or_negative_quantity_raises_validation_error(
    invalid_qty: float,
) -> None:
    """Validate that quantity must be strictly greater than 0 (gt=0)."""
    with pytest.raises(ValidationError) as exc_info:
        PantryItemCreate(
            ingrediente="Arroz",
            cantidad=invalid_qty,
            unidad="kg",
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("cantidad",) for err in errors)


def test_pantry_item_create_empty_ingrediente_or_unidad_raises_validation_error() -> None:
    """Validate that empty strings for required fields trigger min_length=1 validation error."""
    # Ingrediente vacío
    with pytest.raises(ValidationError) as exc_info_1:
        PantryItemCreate(ingrediente="", cantidad=1.0, unidad="kg")
    assert any(err["loc"] == ("ingrediente",) for err in exc_info_1.value.errors())

    # Unidad vacía
    with pytest.raises(ValidationError) as exc_info_2:
        PantryItemCreate(ingrediente="Arroz", cantidad=1.0, unidad="")
    assert any(err["loc"] == ("unidad",) for err in exc_info_2.value.errors())


def test_pantry_item_create_max_length_exceeded_raises_validation_error() -> None:
    """Validate that exceeding max_length constraints triggers ValidationError."""
    long_ingredient = "A" * 121
    long_unit = "U" * 21

    # Ingrediente > 120 caracteres
    with pytest.raises(ValidationError) as exc_info_1:
        PantryItemCreate(ingrediente=long_ingredient, cantidad=1.0, unidad="kg")
    assert any(err["loc"] == ("ingrediente",) for err in exc_info_1.value.errors())

    # Unidad > 20 caracteres
    with pytest.raises(ValidationError) as exc_info_2:
        PantryItemCreate(ingrediente="Sal", cantidad=1.0, unidad=long_unit)
    assert any(err["loc"] == ("unidad",) for err in exc_info_2.value.errors())


def test_pantry_item_create_invalid_date_format_raises_validation_error() -> None:
    """Validate that invalid date formats trigger ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        PantryItemCreate(
            ingrediente="Leche",
            cantidad=1.0,
            unidad="L",
            fecha_caducidad="31-12-2026",  # Formato incorrecto (debe ser YYYY-MM-DD o date)
        )
    assert any(err["loc"] == ("fecha_caducidad",) for err in exc_info.value.errors())


def test_pantry_item_update_valid_partial() -> None:
    """Validate partial update schema allowing optional fields."""
    update_data = PantryItemUpdate(cantidad=2.5)
    dumped = update_data.model_dump(exclude_unset=True)
    assert dumped == {"cantidad": 2.5}
    assert update_data.ingrediente is None


def test_pantry_item_update_invalid_quantity_raises_validation_error() -> None:
    """Validate that setting a non-positive quantity on update fails."""
    with pytest.raises(ValidationError) as exc_info:
        PantryItemUpdate(cantidad=0)
    assert any(err["loc"] == ("cantidad",) for err in exc_info.value.errors())


def test_pantry_item_update_empty_strings_raises_validation_error() -> None:
    """Validate that updating with an empty string for ingrediente or unidad fails."""
    with pytest.raises(ValidationError) as exc_info_1:
        PantryItemUpdate(ingrediente="")
    assert any(err["loc"] == ("ingrediente",) for err in exc_info_1.value.errors())

    with pytest.raises(ValidationError) as exc_info_2:
        PantryItemUpdate(unidad="")
    assert any(err["loc"] == ("unidad",) for err in exc_info_2.value.errors())


def test_user_register_valid() -> None:
    """Validate UserRegister schema with valid data."""
    reg = UserRegister(id_token="valid-firebase-token", nombre="Carlos Gómez")
    assert reg.id_token == "valid-firebase-token"
    assert reg.nombre == "Carlos Gómez"


def test_user_register_empty_token_raises_validation_error() -> None:
    """Validate that empty id_token triggers min_length=1 error."""
    with pytest.raises(ValidationError) as exc_info:
        UserRegister(id_token="")
    assert any(err["loc"] == ("id_token",) for err in exc_info.value.errors())


def test_user_register_name_max_length_exceeded_raises_validation_error() -> None:
    """Validate that nombre exceeding 120 chars fails."""
    with pytest.raises(ValidationError) as exc_info:
        UserRegister(id_token="token-abc", nombre="A" * 121)
    assert any(err["loc"] == ("nombre",) for err in exc_info.value.errors())


def test_user_login_empty_token_raises_validation_error() -> None:
    """Validate that empty id_token in UserLogin / FirebaseLoginRequest fails."""
    with pytest.raises(ValidationError) as exc_info_1:
        UserLogin(id_token="")
    assert any(err["loc"] == ("id_token",) for err in exc_info_1.value.errors())

    with pytest.raises(ValidationError) as exc_info_2:
        FirebaseLoginRequest(id_token="")
    assert any(err["loc"] == ("id_token",) for err in exc_info_2.value.errors())


def test_user_base_invalid_email_format_raises_validation_error() -> None:
    """Validate that malformed email addresses fail EmailStr validation."""
    invalid_emails = ["notanemail", "user@", "@domain.com", "user@domain..com"]
    for email in invalid_emails:
        with pytest.raises(ValidationError) as exc_info:
            UserBase(email=email)
        assert any(err["loc"] == ("email",) for err in exc_info.value.errors())


def test_user_base_valid_email_and_defaults() -> None:
    """Validate UserBase with a valid email and optional fields."""
    user = UserBase(
        email="valid.user@mealmuse.com",
        nombre="Valeria",
        alergias=["gluten", "lactosa"],
        objetivos_nutricionales="Ganancia muscular",
    )
    assert user.email == "valid.user@mealmuse.com"
    assert user.nombre == "Valeria"
    assert user.alergias == ["gluten", "lactosa"]
    assert user.objetivos_nutricionales == "Ganancia muscular"


def test_user_base_objetivos_nutricionales_max_length_exceeded_raises_validation_error() -> None:
    """Validate that objetivos_nutricionales exceeding 500 chars fails."""
    with pytest.raises(ValidationError) as exc_info:
        UserBase(
            email="valid@mealmuse.com",
            objetivos_nutricionales="X" * 501,
        )
    assert any(err["loc"] == ("objetivos_nutricionales",) for err in exc_info.value.errors())


def test_user_update_max_length_constraints() -> None:
    """Validate UserUpdate max_length constraints."""
    with pytest.raises(ValidationError) as exc_info_1:
        UserUpdate(nombre="N" * 121)
    assert any(err["loc"] == ("nombre",) for err in exc_info_1.value.errors())

    with pytest.raises(ValidationError) as exc_info_2:
        UserUpdate(objetivos_nutricionales="O" * 501)
    assert any(err["loc"] == ("objetivos_nutricionales",) for err in exc_info_2.value.errors())
