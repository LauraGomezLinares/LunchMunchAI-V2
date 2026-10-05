# Registro Formal de Pruebas de Integración - Sprint 2

**Proyecto:** MealMuse Backend API  
**Responsable:** QA Engineer & Software Architect  
**Entorno de Ejecución:** Windows 11 / Python 3.12.2 / Pytest 8.3.3 / FastAPI TestClient / SQLite InMemory (StaticPool)  
**Fecha:** 2026-10-05  

---

## 1. Resumen Ejecutivo de Ejecución

| Tipo de Prueba | Total Diseñadas | Aprobadas (Pass) | Fallidas (Fail) | Cobertura de Módulo |
| :--- | :---: | :---: | :---: | :---: |
| **Pruebas de Integración (PI)** | 25 | 25 | 0 | `routers.health` (100%), `routers.auth` (100%), `routers.pantry` (100%) |

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

---

### Módulo: Gestión de Despensa e Inventario Multiusuario (`routers.pantry`)

| ID y Módulo de la Prueba | Descripción del Escenario | Input / Mock Inyectado | Output Esperado | Resultado (Pass/Fail) |
| :--- | :--- | :--- | :--- | :---: |
| **PI-13: Pantry API** | Creación exitosa de ingrediente en `POST /api/v1/pantry/` | `{"ingrediente": "Tomates", "cantidad": 500.0, "unidad": "g", "fecha_caducidad": "2026-10-15"}` + `auth_headers` | `HTTP 201 Created` con objeto `PantryItemRead` conteniendo `id`, `usuario_id` y `created_at` | **PASS** |
| **PI-14: Pantry API** | Rechazo de creación con cantidad no positiva (`cantidad=0`) | `{"ingrediente": "Sal", "cantidad": 0, "unidad": "g"}` | `HTTP 422 Unprocessable Entity` | **PASS** |
| **PI-15: Pantry API** | Rechazo de creación sin autenticación | Petición POST a `/api/v1/pantry/` sin encabezado `Authorization` | `HTTP 401 Unauthorized` | **PASS** |
| **PI-16: Pantry API** | Listado de despensa vacía al iniciar | `GET /api/v1/pantry/` para usuario sin ingredientes | `HTTP 200 OK` con JSON `[]` | **PASS** |
| **PI-17: Pantry API** | Ordenamiento de despensa por fecha de caducidad (`asc().nulls_last()`) | 3 ingredientes con fechas: `"2026-10-25"`, `None`, `"2026-10-10"` | `HTTP 200 OK` retornando lista ordenada: 10/10 $\to$ 25/10 $\to$ `null` | **PASS** |
| **PI-18: Pantry API** | Actualización parcial en `PUT /api/v1/pantry/{item_id}` | `{"cantidad": 6.0}` sobre ítem con cantidad 12.0 | `HTTP 200 OK` con `cantidad=6.0` y demás atributos preservados | **PASS** |
| **PI-19: Pantry API** | Actualización de ingrediente inexistente | `PUT /api/v1/pantry/{uuid_aleatorio}` | `HTTP 404 Not Found` con detalle *"Ingrediente no encontrado"* | **PASS** |
| **PI-20: Pantry API** | Rechazo de cantidad inválida en actualización (`cantidad=-2.0`) | `PUT /api/v1/pantry/{item_id}` con `cantidad=-2.0` | `HTTP 422 Unprocessable Entity` | **PASS** |
| **PI-21: Pantry API** | Eliminación exitosa de ingrediente en `DELETE /api/v1/pantry/{item_id}` | `DELETE /api/v1/pantry/{item_id}` con `auth_headers` | `HTTP 204 No Content`, y exclusión confirmada en listado posterior | **PASS** |
| **PI-22: Pantry API** | Eliminación de ingrediente inexistente | `DELETE /api/v1/pantry/{uuid_aleatorio}` | `HTTP 404 Not Found` con detalle *"Ingrediente no encontrado"* | **PASS** |
| **PI-23: Pantry API (Seguridad Multitenant)** | Aislamiento de listado entre usuarios | Usuario A crea ingredientes. Usuario B consulta `GET /api/v1/pantry/` | `HTTP 200 OK` con `[]` para Usuario B (no ve datos de Usuario A) | **PASS** |
| **PI-24: Pantry API (Seguridad Multitenant)** | Intento de modificación cruzada entre usuarios | Usuario B intenta `PUT /api/v1/pantry/{item_id_usuario_A}` | `HTTP 404 Not Found` impidiendo modificación y fuga de existencia | **PASS** |
| **PI-25: Pantry API (Seguridad Multitenant)** | Intento de eliminación cruzada entre usuarios | Usuario B intenta `DELETE /api/v1/pantry/{item_id_usuario_A}` | `HTTP 404 Not Found`, manteniéndose el ítem intacto para Usuario A | **PASS** |
