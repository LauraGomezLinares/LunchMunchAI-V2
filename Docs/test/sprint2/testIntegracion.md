# Registro Formal de Pruebas de Integración - Sprint 2

**Proyecto:** MealMuse Backend API  
**Responsable:** QA Engineer & Software Architect  
**Entorno de Ejecución:** Windows 11 / Python 3.12.2 / Pytest 8.3.3 / FastAPI TestClient / SQLite InMemory (StaticPool)  
**Fecha:** 2026-10-05  

---

## 1. Resumen Ejecutivo de Ejecución

| Tipo de Prueba | Total Diseñadas | Aprobadas (Pass) | Fallidas (Fail) | Cobertura de Módulo |
| :--- | :---: | :---: | :---: | :---: |
| **Pruebas de Integración (PI)** | 12 | 12 | 0 | `routers.health` (100%), `routers.auth` (100%) |

---

## 2. Matriz Detallada de Pruebas de Integración (Fase 3)

### Módulo: Endpoint de Salud del Sistema (`routers.health`)

| ID y Módulo de la Prueba | Descripción del Escenario | Input / Mock Inyectado | Output Esperado | Resultado (Pass/Fail) |
| :--- | :--- | :--- | :--- | :---: |
| **PI-01: Health API** | Consulta de disponibilidad del servicio en `GET /health` | Petición HTTP GET sin autenticación | `HTTP 200 OK` con JSON `{"status": "ok"}` | **PASS** |

---

### Módulo: Endpoints de Autenticación y Ciclo de Vida de Usuario (`routers.auth`)

| ID y Módulo de la Prueba | Descripción del Escenario | Input / Mock Inyectado | Output Esperado | Resultado (Pass/Fail) |
| :--- | :--- | :--- | :--- | :---: |
| **PI-02: Auth API** | Registro exitoso de usuario nuevo en `POST /api/v1/auth/register` | `{"id_token": "valid-token"}`. Mock de claims: `uid="test-firebase-uid-123"`, `email="tester@mealmuse.com"` | `HTTP 201 Created` con JSON `Token` conteniendo `access_token`, `token_type="bearer"` y objeto `user` persistido | **PASS** |
| **PI-03: Auth API** | Registro con sobreescritura explícita de nombre (`nombre`) | `{"id_token": "valid-token", "nombre": "Nombre Personalizado"}` | `HTTP 201 Created` con `user.nombre == "Nombre Personalizado"` en BD | **PASS** |
| **PI-04: Auth API** | Rechazo de registro cuando el correo en claims tiene formato sintácticamente inválido | `mock_firebase({"uid": "...", "email": "invalid-email-address"})` | `HTTP 422 Unprocessable Entity` con detalle de validación | **PASS** |
| **PI-05: Auth API** | Rechazo de registro por conflicto de correo duplicado (`409 Conflict`) | Primer registro con UID 1 y `shared@mealmuse.com`. Segundo registro con UID 2 y mismo correo | `HTTP 409 Conflict` con detalle *"El correo ya está registrado con otra cuenta."* | **PASS** |
| **PI-06: Auth API** | Inicio de sesión exitoso en `POST /api/v1/auth/login` | `{"id_token": "valid-token"}` para usuario existente | `HTTP 200 OK` con `access_token` firmado y perfil del usuario | **PASS** |
| **PI-07: Auth API** | Autenticación explícita de Firebase en `POST /api/v1/auth/firebase-login` | `{"id_token": "valid-token"}` | `HTTP 200 OK` con `access_token` firmado y `token_type="bearer"` | **PASS** |
| **PI-08: Auth API** | Rechazo en endpoints de autenticación cuando Firebase invalida el token | Mock de `verify_firebase_token` lanzando `HTTPException(401)` | `HTTP 401 Unauthorized` con detalle *"El token de Firebase no es válido o ha expirado."* | **PASS** |
| **PI-09: Auth API** | Consulta de perfil propio autenticado en `GET /api/v1/auth/me` | Encabezado `Authorization: Bearer <valid_jwt>` con usuario pre-sembrado en BD | `HTTP 200 OK` retornando el perfil local con `id`, `email`, `nombre`, `created_at` | **PASS** |
| **PI-10: Auth API** | Intento de consultar `GET /api/v1/auth/me` sin encabezado de autorización | Petición sin encabezado `Authorization` | `HTTP 401 Unauthorized` con detalle *"Se requiere un token Bearer."* | **PASS** |
| **PI-11: Auth API** | Intento de consultar `GET /api/v1/auth/me` con token Bearer inválido/falso | Encabezado `Authorization: Bearer invalid.token.payload` | `HTTP 401 Unauthorized` | **PASS** |
| **PI-12: Auth API** | Cierre de sesión de cliente en `POST /api/v1/auth/logout` | Petición POST a `/api/v1/auth/logout` | `HTTP 204 No Content` con cuerpo vacío | **PASS** |
