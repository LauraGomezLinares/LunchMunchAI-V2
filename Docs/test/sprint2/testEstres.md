# Plan y Registro de Pruebas de Estrés y Rendimiento - Sprint 2

**Proyecto:** MealMuse Backend API  
**Responsable:** QA Engineer & Software Architect  
**Herramienta de Carga:** Locust 2.46.7 (Headless Mode)  
**Servidor de Aplicación:** Uvicorn ASGI Server (FastAPI)  
**Fecha:** 2026-10-05  

---

## 1. Objetivos de Rendimiento y Carga

1. **Evaluar Concurrencia:** Medir el comportamiento del backend ante 50 usuarios concurrentes simulando tráfico móvil.
2. **Distribución de Carga (Weighted Tasks):**
   - **80% del tráfico:** Endpoint ligero de monitoreo y disponibilidad (`GET /health`).
   - **20% del tráfico:** Endpoint protegido de lectura de despensa (`GET /api/v1/pantry/`) con validación de JWT y acceso a base de datos.
3. **Estrategia Zero-Quota Impact:** Generación local de JWT firmados con `jwt_secret` y pre-siembra de usuario de prueba para evitar consumo de cuotas de Firebase Admin SDK.
4. **Criterios de Aceptación (SLA):**
   - Tasa de error (Failure Rate): $< 1\%$.
   - Tiempo de respuesta p95: $< 200 \text{ ms}$ en `/health` y $< 500 \text{ ms}$ en `/api/v1/pantry/`.
   - Rendimiento sostenido: $\ge 30 \text{ RPS}$ (Requests Per Second).

---

## 2. Parámetros de Ejecución del Escenario (PE-01)

| Parámetro | Valor Configurado | Justificación |
| :--- | :--- | :--- |
| **Usuarios Concurrentes (`-u`)** | 50 usuarios | Simulación de pico de tráfico móvil en hora pico. |
| **Tasa de Crecimiento (`-r`)** | 5 usuarios / segundo | Rampa suave para alcanzar la carga máxima en 10 segundos. |
| **Duración de la Prueba (`-t`)** | 30 segundos (`30s`) | Ventana suficiente para estabilizar métricas de percentiles (p50, p95, p99). |
| **Modo de Ejecución** | Headless (`--headless`) | Ejecución automatizada sin interfaz gráfica para reportes CI/CD. |
| **Host Objetivo** | `http://127.0.0.1:8000` | Instancia local del servidor Uvicorn. |
| **Reporte de Salida** | `tests/reportes/test/sprint2/report_estres.html` | Reporte visual HTML autocontenido con gráficos de latencia y RPS. |

---

## 3. Matriz de Escenarios de Estrés (Fase 4)

| ID y Módulo de la Prueba | Descripción del Escenario | Distribución de Tráfico | Métrica Clave | Criterio de Éxito |
| :--- | :--- | :---: | :--- | :---: |
| **PE-01: Healthcheck Load** | Lectura masiva no autenticada en `GET /health` | 80% del total | Latencia media y p95 | p95 $< 200\text{ ms}$, 0% fallos |
| **PE-02: Pantry Inventory Load** | Lectura concurrente autenticada en `GET /api/v1/pantry/` | 20% del total | Latencia con BD y JWT | p95 $< 500\text{ ms}$, 0% fallos |

---

## 4. Instrucciones de Ejecución Local

### Terminal 1: Iniciar Servidor Backend (Uvicorn)
```powershell
cd c:\Proyectos\Universidad\Ciclo_9\Integrador\LunchMunchAI-V2-1\backend
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000
```

### Terminal 2: Ejecutar Locust en Modo Headless
```powershell
cd c:\Proyectos\Universidad\Ciclo_9\Integrador\LunchMunchAI-V2-1\backend
.\.venv\Scripts\locust.exe -f tests/performance/locustfile.py --headless -u 50 -r 5 --run-time 30s --host http://127.0.0.1:8000 --html tests/reportes/test/sprint2/report_estres.html
```
