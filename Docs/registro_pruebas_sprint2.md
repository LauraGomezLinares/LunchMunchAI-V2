# Registro Formal de Pruebas de Software - Sprint 2

**Proyecto:** MealMuse Backend API  
**Responsable:** QA Engineer & Software Architect  
**Entorno de Ejecución:** Windows 11 / Python 3.12.2 / Pytest 8.3.3  
**Fecha:** 2026-10-05  

---

## 1. Resumen Ejecutivo de Ejecución

| Tipo de Prueba | Total Diseñadas | Aprobadas (Pass) | Fallidas (Fail) | Cobertura de Módulo |
| :--- | :---: | :---: | :---: | :---: |
| **Pruebas Unitarias (PU)** | 40 | 40 | 0 | `app.core.security` (100%), `app.services.auth_service` (100%), `app.schemas` (100%) |
| **Pruebas de Integración (PI)** | 0 (Pendiente) | 0 | 0 | - |
| **Pruebas de Rendimiento (PE)** | 0 (Pendiente) | 0 | 0 | - |

---

## 2. Matriz Detallada de Pruebas Unitarias (Fase 2)

### Módulo: Seguridad y Autenticación (`app.core.security`)

| ID y Módulo de la Prueba | Descripción del Escenario | Input / Mock Inyectado | Output Esperado | Resultado (Pass/Fail) |
| :--- | :--- | :--- | :--- | :---: |
| **PU-01: Security Core** | Validación de codificación y estructura del token JWT (`create_access_token`) | `subject="user-firebase-123"`, `claims={"email": "tester@mealmuse.com", "role": "admin"}` | Token firmado con `sub`, `email`, `role`, `iat` y `exp` verificables con `jwt_secret` | **PASS** |
| **PU-02: Security Core** | Decodificación exitosa de token JWT válido (`_decode_access_token`) | `token` activo emitido por la aplicación para `user-valid-jwt` | Diccionario deserializado con `sub="user-valid-jwt"` y `email="valid@mealmuse.com"` | **PASS** |
| **PU-03: Security Core** | Rechazo de token JWT expirado (`_decode_access_token`) | Token JWT generado con timestamp de expiración (`exp`) con 2 horas en el pasado | `HTTPException(401)` con detalle *"El token de acceso no es válido o ha expirado."* | **PASS** |
| **PU-04: Security Core** | Rechazo de token JWT con firma criptográfica alterada o inválida | Token firmado con clave secreta no autorizada (`"wrong-secret-key"`) | `HTTPException(401)` con detalle *"El token de acceso no es válido o ha expirado."* | **PASS** |
| **PU-05: Security Core** | Verificación exitosa de Firebase ID token (`verify_firebase_token`) | `id_token="fake-firebase-id-token"`. Mock de `firebase_admin.auth.verify_id_token` retornando `uid` y `email` | Diccionario con claims decodificados de Firebase (`uid="fb-uid-999"`) | **PASS** |
| **PU-06: Security Core** | Manejo de excepción ante Firebase ID token inválido o corrupto | `id_token="invalid-token"`. Mock de `firebase_admin.auth.verify_id_token` lanzando `ValueError` | `HTTPException(401)` con detalle *"El token de Firebase no es válido o ha expirado."* | **PASS** |
| **PU-07: Security Core** | Intento de resolver usuario actual sin encabezado de autorización (`get_current_user`) | `credentials_data=None` | `HTTPException(401)` con detalle *"Se requiere un token Bearer."* | **PASS** |
| **PU-08: Security Core** | Resolución de usuario actual a partir de JWT local válido (`get_current_user`) | `HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid.jwt.token")`. Mock de `_decode_access_token` y `get_user_by_firebase_uid` | Objeto `User` instanciado correctamente sin consultar base de datos física | **PASS** |
| **PU-09: Security Core** | Fallback a Firebase ID token cuando la decodificación de JWT local falla | `credentials="raw.firebase.token"`. Mock de `_decode_access_token` fallando y `verify_firebase_token` exitoso | Objeto `User` recuperado mediante los claims de Firebase tras activar mecanismo de fallback | **PASS** |
| **PU-10: Security Core** | Rechazo de autenticación cuando el usuario del token no existe en la base de datos | `credentials="valid.jwt.token"`. Mock de `get_user_by_firebase_uid` retornando `None` | `HTTPException(401)` con detalle *"El usuario autenticado no existe."* | **PASS** |

---

### Módulo: Lógica de Negocio de Autenticación (`app.services.auth_service`)

| ID y Módulo de la Prueba | Descripción del Escenario | Input / Mock Inyectado | Output Esperado | Resultado (Pass/Fail) |
| :--- | :--- | :--- | :--- | :---: |
| **PU-11: Auth Service** | Normalización de email a minúsculas en búsqueda local (`get_user_by_email`) | `email="TEST@MEALMUSE.COM"`. Mock de `Session.exec` retornando `User` | Consulta SQL filtrando exactamente por `test@mealmuse.com` | **PASS** |
| **PU-12: Auth Service** | Búsqueda de usuario por UID de Firebase (`get_user_by_firebase_uid`) | `firebase_uid="fb-uid-100"`. Mock de `Session.exec` | Retorno de objeto `User` correspondiente al UID buscado | **PASS** |
| **PU-13: Auth Service** | Creación exitosa de usuario nuevo desde claims válidos de Firebase (`create_user_from_firebase`) | Claims: `uid="fb-new-user"`, `email="NEWUSER@MEALMUSE.COM"`, `name="New User Name"`. Mocks de búsqueda retornando `None` | Usuario creado con email en minúsculas, agregado a sesión (`session.add`), persistido (`commit`) y refrescado (`refresh`) | **PASS** |
| **PU-14: Auth Service** | Actualización de perfil para usuario ya existente sincronizado (`create_user_from_firebase`) | Claims con UID ya existente y nombre nuevo. Mock retornando usuario existente | Perfil actualizado con nuevo nombre y timestamp `updated_at`, ejecutando `commit` y `refresh` | **PASS** |
| **PU-15: Auth Service** | Rechazo de claims incompletos sin UID o sin Email | Claims faltantes: `{"uid": "user-123"}` (sin email) o `{"email": "..."}` (sin uid) | `HTTPException(401)` con detalle *"El token no contiene una identidad válida."* | **PASS** |
| **PU-16: Auth Service** | Rechazo de claims con formato de correo sintácticamente inválido | Claims con `email="invalid-not-an-email"` | `HTTPException(422)` con detalle *"El correo de Firebase no tiene un formato válido."* | **PASS** |
| **PU-17: Auth Service** | Prevención de conflicto por correo duplicado asignado a otra cuenta | Intento de registro con UID de atacante pero con email perteneciente a otro usuario existente | `HTTPException(409)` con detalle *"El correo ya está registrado con otra cuenta."* | **PASS** |
| **PU-18: Auth Service** | Delegación de creación de JWT a módulo de seguridad (`create_access_token`) | Objeto `User(firebase_uid="uid-abc", email="user@mealmuse.com")` | Invocación a `security.create_access_token` con UID y diccionario de claims | **PASS** |
| **PU-19: Auth Service** | Orquestación de registro de usuario (`register_user`) | `id_token="raw-id-token"`, `nombre="Reg Name"`. Mock de `verify_firebase_token` | Sincronización y persistencia delegadas a `create_user_from_firebase` | **PASS** |
| **PU-20: Auth Service** | Delegación de autenticación de usuario (`authenticate_user`) | `id_token="raw-id-token"`. Mock de `register_user` | Invocación directa a `register_user(session, id_token)` | **PASS** |
| **PU-21: Auth Service** | Cierre de sesión y revocación exitosa de tokens en Firebase (`revoke_firebase_token`) | `id_token="valid-id-token"`. Mock de `verify_firebase_token` retornando claims | Invocación a `firebase_admin.auth.revoke_refresh_tokens(claims["uid"])` | **PASS** |
| **PU-22: Auth Service** | Manejo de excepción durante la revocación de tokens en Firebase | Mock de `firebase_admin.auth.revoke_refresh_tokens` lanzando `ValueError` | `HTTPException(401)` con detalle *"No se pudo cerrar la sesión de Firebase."* | **PASS** |

---

### Módulo: Esquemas y Validación de Datos (`app.schemas`)

| ID y Módulo de la Prueba | Descripción del Escenario | Input / Mock Inyectado | Output Esperado | Resultado (Pass/Fail) |
| :--- | :--- | :--- | :--- | :---: |
| **PU-23: Schemas Pantry** | Creación válida de `PantryItemCreate` con todos los campos | `ingrediente="Zanahorias"`, `cantidad=500.0`, `unidad="g"`, `fecha_caducidad="2026-11-20"` | Instancia creada correctamente con `date(2026, 11, 20)` | **PASS** |
| **PU-24: Schemas Pantry** | Rechazo de cantidad igual a cero (`cantidad=0`) en `PantryItemCreate` | `cantidad=0`, `ingrediente="Arroz"`, `unidad="kg"` | `ValidationError` indicando `Input should be greater than 0` (`gt=0`) | **PASS** |
| **PU-25: Schemas Pantry** | Rechazo de cantidad negativa (`cantidad=-1`) en `PantryItemCreate` | `cantidad=-1`, `ingrediente="Arroz"`, `unidad="kg"` | `ValidationError` indicando `Input should be greater than 0` (`gt=0`) | **PASS** |
| **PU-26: Schemas Pantry** | Rechazo de cantidad decimal negativa (`cantidad=-0.01`) en `PantryItemCreate` | `cantidad=-0.01`, `ingrediente="Arroz"`, `unidad="kg"` | `ValidationError` indicando `Input should be greater than 0` (`gt=0`) | **PASS** |
| **PU-27: Schemas Pantry** | Rechazo de cadenas vacías en campos obligatorios de `PantryItemCreate` | `ingrediente=""` o `unidad=""` | `ValidationError` por incumplimiento de `min_length=1` | **PASS** |
| **PU-28: Schemas Pantry** | Rechazo de exceso de longitud en campos de texto de `PantryItemCreate` | `ingrediente="A"*121` o `unidad="U"*21` | `ValidationError` por incumplimiento de `max_length` (120 y 20 resp.) | **PASS** |
| **PU-29: Schemas Pantry** | Rechazo de formato de fecha inválido en `PantryItemCreate` | `fecha_caducidad="31-12-2026"` (formato no ISO) | `ValidationError` en campo `fecha_caducidad` | **PASS** |
| **PU-30: Schemas Pantry** | Actualización parcial válida en `PantryItemUpdate` | `PantryItemUpdate(cantidad=2.5)` | `model_dump(exclude_unset=True)` retorna solo `{"cantidad": 2.5}` | **PASS** |
| **PU-31: Schemas Pantry** | Rechazo de cantidad no positiva en actualización `PantryItemUpdate` | `cantidad=0` | `ValidationError` por violación de `gt=0` | **PASS** |
| **PU-32: Schemas Pantry** | Rechazo de cadenas vacías en campos actualizables de `PantryItemUpdate` | `ingrediente=""` o `unidad=""` | `ValidationError` por `min_length=1` | **PASS** |
| **PU-33: Schemas Auth** | Instanciación válida de `UserRegister` | `id_token="valid-token"`, `nombre="Carlos Gómez"` | Objeto creado con token y nombre asignados | **PASS** |
| **PU-34: Schemas Auth** | Rechazo de `id_token` vacío en `UserRegister` | `id_token=""` | `ValidationError` por incumplimiento de `min_length=1` | **PASS** |
| **PU-35: Schemas Auth** | Rechazo de nombre con más de 120 caracteres en `UserRegister` | `nombre="A"*121` | `ValidationError` por violación de `max_length=120` | **PASS** |
| **PU-36: Schemas Auth** | Rechazo de `id_token` vacío en `UserLogin` y `FirebaseLoginRequest` | `id_token=""` | `ValidationError` por `min_length=1` | **PASS** |
| **PU-37: Schemas User** | Rechazo de formato de correo inválido en `UserBase` (`EmailStr`) | Correos: `"notanemail"`, `"user@"`, `"@domain.com"` | `ValidationError` emitido por el validador `EmailStr` de Pydantic | **PASS** |
| **PU-38: Schemas User** | Instanciación válida de `UserBase` con correo y metadatos | `email="valid.user@mealmuse.com"`, alergias y objetivos | Instanciación correcta de campos y estructuras JSON/List | **PASS** |
| **PU-39: Schemas User** | Rechazo de objetivos nutricionales que exceden 500 caracteres | `objetivos_nutricionales="X"*501` | `ValidationError` por violación de `max_length=500` | **PASS** |
| **PU-40: Schemas User** | Restricciones de longitud máxima en `UserUpdate` | `nombre="N"*121` u `objetivos_nutricionales="O"*501` | `ValidationError` por superación de límites `max_length` | **PASS** |

---

## 3. Registro de Hallazgos y Refactorizaciones Pedagógicas

- **Hallazgo Crítico en `app.core.security.get_current_user` (Sprint 2 / Fase 2.1):**
  - *Diagnóstico:* Se detectó que el mecanismo de *fallback* para soportar tanto JWTs locales como ID tokens directos de Firebase estaba bloqueado. Al fallar `_decode_access_token`, se capturaba la excepción `HTTPException` y se relanzaba de inmediato (`raise`), impidiendo que el flujo alcanzara la llamada a `verify_firebase_token(token)`.
  - *Refactorización Aplicada:* Se rediseñó el bloque `try/except` para intentar primero la resolución del token JWT local y, en caso de fallo, capturar la excepción y verificar el token contra Firebase Admin SDK antes de emitir el error `401 Unauthorized`.
