# AstroVitals Production & Operational Guide (FastAPI Edition)

## 1. Executive Architecture Overview

AstroVitals is an offline-first, mission-critical astronaut health monitoring backend built with Python 3.12+, FastAPI, Uvicorn, and an embedded SQLite storage engine (`aiosqlite`). It operates in resource-constrained, disconnected environments (spacecraft, habitat, EVA suits) while delivering low-latency telemetry ingestion, real-time deterministic alert rule evaluation, in-process CPU-bound ML anomaly assessment, streaming Server-Sent Events (SSE), and eventual outbox synchronization.

```
                              +-------------------------+
                              |   Wearable / Sensor /   |
                              |   Replay / Simulator    |
                              +------------+------------+
                                           | HTTP Ingest (POST /telemetry)
                                           v
+-----------------------------------------------------------------------------------+
| AstroVitals Node (FastAPI / 1 Uvicorn Worker)                                     |
|                                                                                   |
|  +---------------------+        +--------------------+        +----------------+  |
|  |   FastAPI Router    | -----> |   Ingest Service   | -----> |   Domain Rule  |  |
|  |  + ASGIMiddleware   |        +----+----------+----+        |   Engine       |  |
|  +---------------------+             |          |             +-------+--------+  |
|            |                         |          v                     |           |
|            |                         |  +--------------------+        |           |
|            |                         |  |   In-Process ML    |        v           |
|            |                         |  | Predictor (Thread) |  +--------------+  |
|            |                         |  +----------+---------+  | Open/Resolve |  |
|            |                         |             |            | Alert State  |  |
|            |                         v             v            +-------+------+  |
|            |                    +--------------------+                  |         |
|            |                    | Transactional DB   | <----------------+         |
|            |                    | (Telemetry+Outbox) |                            |
|            v                    +---------+----------+                            |
|  +---------------------+                  |                                       |
|  |   SSE Event Hub     | <----------------+                                       |
|  +----------+----------+                                                          |
+-------------|---------------------------------------------------------------------+
              | SSE Stream (/stream)
              v
     +-----------------+
     | Mission Control |
     | / Dashboard / 3D|
     +-----------------+
```

---

## 2. Production Deployment & Build Requirements

### 2.1 Prerequisites
- **Python Version:** Python 3.12+ (or Python 3.13)
- **Dependency Manager:** `uv`
- **Uvicorn Workers:** Exactly **1 worker** (`--workers 1`). The in-memory SSE hub, simulator, and write lock are in-process.

### 2.2 Execution
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8998 --workers 1 --no-access-log
```

### 2.3 Docker Deployment
```dockerfile
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -r pyproject.toml

COPY . .

VOLUME ["/data"]
ENV DB_PATH=/data/astrovitals.db
ENV APP_ENV=prod
ENV HTTP_HOST=0.0.0.0
ENV HTTP_PORT=8998

EXPOSE 8998
USER nobody

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8998", "--workers", "1", "--no-access-log"]
```

---

## 3. Configuration Management

Configuration is loaded from environment variables using `pydantic-settings`:

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_ENV` | string | `dev` | `prod` (JSON structured logging) or `dev` (console colored log) |
| `HTTP_HOST` | string | `0.0.0.0` | Listen host |
| `HTTP_PORT` | int | `8998` | Listen port |
| `DB_PATH` | string | `./data/astrovitals.db` | Filesystem path to SQLite file |
| `CORS_ORIGINS` | string | `*` | Comma-separated allowed origins |
| `ALERT_SUSTAIN_SAMPLES` | int | `3` | Anomaly samples required before alert opens |
| `ALERT_RESOLVE_SAMPLES` | int | `5` | In-range samples required before alert resolves |
| `SIM_INTERVAL_MS` | int | `1000` | Simulator tick interval |
| `ML_ENABLED` | bool | `true` | Enable in-process ML inference |
| `ML_WINDOW_SAMPLES` | int | `30` | Historical window size passed to predictor |
| `ML_EVERY_N_SAMPLES` | int | `5` | Cadence of ML inference per astronaut |
| `ML_TIMEOUT_MS` | int | `500` | Inference timeout in worker thread |
| `ML_ALERT_THRESHOLD` | float | `0.8` | Risk score threshold to trigger AI alert |
| `SYNC_REMOTE_URL` | string | `""` | Remote sync target URL |
| `API_KEY` | string | `""` | Optional API key required on mutating requests |

---

## 4. In-Process ML Architecture & Reliability

1. **Isolation:** ML inference is executed in a dedicated worker thread via `anyio.to_thread.run_sync` wrapped in `asyncio.timeout(0.5)`. The asyncio event loop is never blocked.
2. **In-Flight Guard:** At most one inference task runs simultaneously per astronaut.
3. **Resilience & Fallback:** If ML fails or model files are missing, the system falls back to `NullPredictor`. The backend boots and operates deterministically under rule-based alerting.
4. **Health Reporting:** `/readyz` explicitly reports `"ml_loaded": true/false`.
