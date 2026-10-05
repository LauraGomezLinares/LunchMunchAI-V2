"""Locust performance and load testing scenarios for MealMuse API."""

import logging
from locust import HttpUser, between, task
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import engine, init_db
from app.models.user import User

logger = logging.getLogger(__name__)

# EXPLICACIÓN ARQUITECTÓNICA (POR QUÉ Y CÓMO):
# 1. Estrategia de Autenticación Segura (Zero-Quota Impact):
#    Para evitar agotar las cuotas de Google Firebase Admin SDK durante pruebas de estrés
#    con cientos de peticiones por segundo, generamos tokens JWT firmados localmente
#    con `jwt_secret` del entorno.
# 2. Pre-siembra de Usuario (Idempotente):
#    Aseguramos que el usuario de prueba de carga exista en la base de datos local SQLite
#    para que el endpoint `/api/v1/pantry/` valide la sesión sin fallos 401.


def _ensure_performance_test_user() -> tuple[str, str]:
    """Ensure a dedicated load-testing user exists in the local database and return its token."""
    init_db()
    test_uid = "locust-load-test-uid"
    test_email = "locust.tester@mealmuse.com"

    with Session(engine) as session:
        user = session.exec(select(User).where(User.firebase_uid == test_uid)).first()
        if not user:
            user = User(
                firebase_uid=test_uid,
                email=test_email,
                nombre="Locust Load Tester",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info("Created locust load-testing user: %s", user.email)

    token = create_access_token(test_uid, {"email": test_email})
    return test_uid, token


class MealMuseApiUser(HttpUser):
    """Simulates realistic concurrent mobile client traffic with weighted tasks."""

    # Tiempo de espera simulado entre peticiones (entre 0.5 y 1.5 segundos)
    wait_time = between(0.5, 1.5)

    def on_start(self) -> None:
        """Initialize user session and authentication headers before firing requests."""
        _, token = _ensure_performance_test_user()
        self.auth_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    @task(4)
    def test_health_check(self) -> None:
        """Weight 80%: Query lightweight healthcheck endpoint."""
        self.client.get("/health", name="[GET] /health")

    @task(1)
    def test_list_pantry(self) -> None:
        """Weight 20%: Query user pantry inventory with JWT authentication."""
        self.client.get(
            "/api/v1/pantry/",
            headers=self.auth_headers,
            name="[GET] /api/v1/pantry/",
        )
