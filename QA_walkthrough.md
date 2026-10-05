# QA Walkthrough & Architectural Testing Blueprint

**Proyecto:** MealMuse Backend API (FastAPI + SQLModel + Firebase)  
**Rol:** QA Engineer & Software Architect  
**Fecha de actualización:** 2026-10-05  

---

## 1. Diagnóstico Arquitectónico y Testabilidad

| Módulo / Capa | Estado Actual | Evaluación para QA y Testing |
| :--- | :--- | :--- |
| **Inyección de Dependencias (FastAPI)** | `Depends(get_session)`, `Depends(get_current_user)` | **Excelente**: Permite sobreescribir la base de datos y la identidad del usuario mediante `app.dependency_overrides` sin modificar el código en producción. |
| **Capa de Autenticación (`auth`)** | `routers/auth.py` $\to$ `services/auth_service.py` $\to$ `core/security.py` | **Muy Bueno**: Separación adecuada de responsabilidades. La lógica de negocio está en el servicio, permitiendo pruebas unitarias puras. |
| **Capa de Despensa (`pantry`)** | `routers/pantry.py` interactúa directamente con `db.exec`, `db.add`, `db.delete` | **Deuda Técnica**: Falta un `services/pantry_service.py`. La lógica de base de datos está embebida en el router, lo que requiere pruebas de integración con base de datos en memoria para verificar su comportamiento. |
| **Dependencia Externa (Firebase Admin)** | `verify_firebase_token` y `_firebase_app` | **Aislamiento Requerido**: El testing no debe depender de conexiones de red a Google Firebase ni de credenciales en variables de entorno. Debe ser mockeado en la frontera del servicio. |
| **Modelos de Datos (`models/pantry.py`)** | Uso de `datetime.utcnow` | **Mejora Identificada**: `datetime.utcnow` está deprecado en Python 3.12+. Debe migrarse a `datetime.now(timezone.utc)` para mantener consistencia con `models/user.py`. |

---

## 2. Estrategia de Testing (Pirámide de Pruebas)

```
             / \
            /   \       [ 3. Pruebas de Estrés / Carga ] -> Locust
           /-----\
          /       \     [ 2. Pruebas de Integración ]   -> Pytest + TestClient (HTTPX) + SQLite StaticPool
         /---------\
        /           \   [ 1. Pruebas Unitarias ]        -> Pytest + Mocks aislados (Unit)
       /-------------\
```

---

## 3. Puesta a Punto del Entorno Local (Instalación y Verificación)

### 3.1. Diagnóstico del Entorno Python
- **Versión de Python detectada en el sistema:** Python 3.12.2 (`py -3.12`).  
- *Justificación arquitectónica:* Se utilizó estrictamente **Python 3.12** conforme a las directrices del proyecto para evitar incompatibilidades de wheels binarios en dependencias clave (`pydantic-core`, `greenlet`, `cryptography`).

### 3.2. Comandos de Instalación Ejecutados (Windows / PowerShell)

```powershell
# 1. Creación del entorno virtual aislado con Python 3.12 en backend/.venv
py -3.12 -m venv c:\Proyectos\Universidad\Ciclo_9\Integrador\LunchMunchAI-V2-1\backend\.venv

# 2. Actualización de pip e instalación de dependencias del backend + QA Stack
& "c:\Proyectos\Universidad\Ciclo_9\Integrador\LunchMunchAI-V2-1\backend\.venv\Scripts\pip.exe" install -r "c:\Proyectos\Universidad\Ciclo_9\Integrador\LunchMunchAI-V2-1\backend\requirements.txt" pytest-mock locust
```

### 3.3. Paquetes Instalados y Funcionalidad en QA
- **Core / Web:** `fastapi==0.115.0`, `uvicorn[standard]==0.32.0`, `starlette==0.38.6`
- **ORM & DB:** `sqlmodel==0.0.22`, `sqlalchemy==2.0.54`, `alembic==1.13.3`
- **Validación & Config:** `pydantic==2.9.2`, `pydantic-settings==2.6.0`, `email-validator==2.2.0`
- **Seguridad & Auth:** `firebase-admin==6.5.0`, `python-jose==3.3.0`, `passlib==1.7.4`, `cryptography==50.0.2`
- **QA & Testing:**
  - `pytest==8.3.3`: Runner principal de pruebas.
  - `pytest-mock==3.16.0`: Utilidad avanzada para aislamiento y mocks de servicios/APIs externas.
  - `httpx==0.27.2`: Cliente HTTP para pruebas de integración con `TestClient`.
  - `locust==2.46.7`: Framework para pruebas de carga, rendimiento y estrés.

### 3.4. Pruebas de Verificación y Compilación
1. **Verificación de importación de la aplicación:**
   ```powershell
   & "backend/.venv/Scripts/python.exe" -c "import app.main; print('Backend loaded successfully!')"
   # Resultado: Backend loaded successfully! (Código de salida: 0)
   ```
2. **Ejecución de suite existente con Pytest:**
   ```powershell
   & "backend/.venv/Scripts/pytest.exe"
   # Resultado: 12 passed en 0.31s (Código de salida: 0)
   ```
3. **Levantamiento del servidor Uvicorn y prueba de endpoint `/health`:**
   ```powershell
   & "backend/.venv/Scripts/uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000
   Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
   # Resultado: {"status": "ok"} (HTTP 200 OK)
   ```

---

## 4. Estado de Avance: Fase 1 (Estructura y Fixtures)

### 4.1. Estructura de Directorios Creada

```
backend/
└── tests/
    ├── conftest.py              # Fixtures compartidas y configuración central de testing
    ├── unit/                    # Pruebas unitarias puras (Mocks de servicios y seguridad)
    │   └── __init__.py
    ├── integration/             # Pruebas de integración HTTP + BD SQLite en memoria
    │   └── __init__.py
    ├── performance/             # Pruebas de carga y estrés con Locust
    │   └── __init__.py
    ├── test_auth.py             # (Pruebas legadas existentes - 12 passed)
    └── test_pantry.py           # (Pruebas legadas existentes)
```

---

### 4.2. Código Fuente Implementado: `backend/tests/conftest.py`

```python
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
```

---

## 5. Fase 2: Pruebas Unitarias (En Progreso)

### 5.1. Política Estricta de Ramas (Branching)
- **Rama Principal de Pruebas (`sprint2/test`):** Rama base donde únicamente se escribe código dentro de la carpeta `backend/tests/`. Si un test falla por un bug en el código de producción, el test DEBE permanecer en estado `FAILED` evidenciando el fallo. Está prohibido modificar código de producción en esta rama.
- **Ramas de Resolución (`sprint2/test/fix-<nombre_del_archivo>`):** Ramas temporales creadas específicamente para aplicar parches al backend tras notificar y autorizar el error detectado. Los commits llevan exclusivamente el nombre del módulo afectado (ej. `core.security`).

### 5.2. Ejecución y Reporte Visual de `tests/unit/test_security.py`

1. **Instalación del generador de reportes visuales:**
   ```powershell
   & "backend/.venv/Scripts/pip.exe" install pytest-html
   ```

2. **Ejecución de la suite con reporte HTML autocontenido:**
   ```powershell
   & "backend/.venv/Scripts/pytest.exe" tests/unit/test_security.py -v --html=report.html --self-contained-html
   ```
- **Resultado:** 10 de 10 pruebas unitarias aprobadas (**10 PASSED**).
- **Reporte generado:** `backend/report.html`

### 5.3. Ejecución y Reporte Visual de `tests/unit/test_auth_service.py`

- **Comando ejecutado:**
  ```powershell
  & "backend/.venv/Scripts/pytest.exe" tests/unit/test_auth_service.py -v --html=report_auth_service.html --self-contained-html
  ```
- **Resultado:** 12 de 12 pruebas unitarias aprobadas (**12 PASSED**).
- **Reporte generado:** `backend/report_auth_service.html`
- **Detalle formal registrado:** [Docs/registro_pruebas_sprint2.md](file:///c:/Proyectos/Universidad/Ciclo_9/Integrador/LunchMunchAI-V2-1/Docs/registro_pruebas_sprint2.md) (Casos PU-11 a PU-22).

### 5.4. Próximos Pasos en Fase 2
1. `tests/unit/test_schemas.py` (Validación de invariantes en esquemas Pydantic).
