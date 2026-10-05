# Registro Formal de Pruebas de Software - Sprint 2

**Proyecto:** MealMuse Backend API  
**Responsable:** QA Engineer & Software Architect  
**Entorno de Ejecución:** Windows 11 / Python 3.12.2 / Pytest 8.3.3  
**Fecha:** 2026-10-05  

---

## 1. Resumen Ejecutivo de Ejecución

| Tipo de Prueba | Total Diseñadas | Aprobadas (Pass) | Fallidas (Fail) | Cobertura de Módulo |
| :--- | :---: | :---: | :---: | :---: |
| **Pruebas Unitarias (PU)** | 10 | 10 | 0 | `app.core.security` (100%) |
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

## 3. Registro de Hallazgos y Refactorizaciones Pedagógicas

- **Hallazgo Crítico en `app.core.security.get_current_user`:**
  - *Diagnóstico:* Se detectó que el mecanismo de *fallback* para soportar tanto JWTs locales como ID tokens directos de Firebase estaba bloqueado. Al fallar `_decode_access_token`, se capturaba la excepción `HTTPException` y se relanzaba de inmediato (`raise`), impidiendo que el flujo alcanzara la llamada a `verify_firebase_token(token)`.
  - *Refactorización Aplicada:* Se rediseñó el bloque `try/except` para intentar primero la resolución del token JWT local y, en caso de fallo, capturar la excepción y verificar el token contra Firebase Admin SDK antes de emitir el error `401 Unauthorized`.
