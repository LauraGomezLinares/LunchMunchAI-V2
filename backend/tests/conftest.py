"""Shared test configuration and reusable fixtures for unit and integration testing."""

from collections.abc import Generator
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.security import create_access_token
from app.db.session import get_session
from app.main import app
from app.models.user import User
from app.services import auth_service

# EXPLICACIÓN ARQUITECTÓNICA (POR QUÉ Y CÓMO):
# Usamos un motor SQLite en memoria ("sqlite://") junto con `StaticPool`.
# ¿POR QUÉ?: SQLite en memoria vive únicamente mientras la conexión permanezca abierta.
# `StaticPool` obliga a SQLAlchemy a compartir exactamente una sola conexión en memoria
# a través de todos los hilos/solicitudes de FastAPI TestClient, evitando que se pierdan
# las tablas creadas entre la llamada de setup y los endpoints HTTP.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(name="db_session")
def db_session_fixture() -> Generator[Session, None, None]:
    """Provide an isolated, clean in-memory database session per test."""
    # Creamos el esquema completo en memoria antes de ejecutar el test
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    # Limpiamos el esquema al finalizar para garantizar total aislamiento
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="mock_firebase")
def mock_firebase_fixture(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, Any] | None], dict[str, Any]]:
    """Mock Firebase ID token verification at the service boundary."""
    default_claims: dict[str, Any] = {
        "uid": "test-firebase-uid-123",
        "email": "tester@mealmuse.com",
        "name": "MealMuse Tester",
    }

    def _set_claims(custom_claims: dict[str, Any] | None = None) -> dict[str, Any]:
        claims = default_claims.copy()
        if custom_claims:
            claims.update(custom_claims)
        # EXPLICACIÓN ARQUITECTÓNICA (POR QUÉ Y CÓMO):
        # Mockeamos la función en el límite de la capa de servicio (auth_service)
        # y de seguridad (core.security). De esta manera, evitamos llamadas de red reales a Google
        # y eliminamos la necesidad de credenciales de Firebase en el entorno de pruebas.
        monkeypatch.setattr(auth_service, "verify_firebase_token", lambda _: claims)
        return claims

    _set_claims()
    return _set_claims


@pytest.fixture(name="test_user")
def test_user_fixture(db_session: Session) -> User:
    """Create and return a pre-seeded test user in the isolated database."""
    user = User(
        firebase_uid="test-firebase-uid-123",
        email="tester@mealmuse.com",
        nombre="MealMuse Tester",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(test_user: User) -> dict[str, str]:
    """Generate valid Bearer authorization headers for the pre-seeded test user."""
    # Generamos un JWT firmado usando la clave secreta y algoritmo configurados en la app
    token = create_access_token(str(test_user.firebase_uid), {"email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="client")
def client_fixture(
    db_session: Session,
    mock_firebase: Callable[..., Any],
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden database session and mocked Firebase."""
    def _override_get_session() -> Generator[Session, None, None]:
        yield db_session

    # Inyectamos la sesión de base de datos en memoria reemplazando la dependencia real
    app.dependency_overrides[get_session] = _override_get_session

    with TestClient(app) as test_client:
        yield test_client

    # Limpiamos las dependencias sobreescritas para no contaminar otras pruebas
    app.dependency_overrides.clear()
