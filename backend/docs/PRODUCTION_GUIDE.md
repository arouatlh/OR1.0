# AstroVitals Production & Operational Guide

## 1. Executive Architecture Overview

AstroVitals is an offline-first, mission-critical astronaut health monitoring backend built with Go, net/http, Chi router, and an embedded pure-Go SQLite storage engine (`modernc.org/sqlite`). It is engineered to operate autonomously in resource-constrained, disconnected environments (e.g., spacecraft, lunar/Mars habitats, EVA suits) while guaranteeing low-latency telemetry ingestion, real-time deterministic alert rule evaluation, streaming updates via Server-Sent Events (SSE), and eventual synchronization via a local outbox.

```
                              +-------------------------+
                              |   Wearable / Sensor /   |
                              |   Replay / Simulator    |
                              +------------+------------+
                                           | HTTP Ingest (POST /telemetry)
                                           v
+-----------------------------------------------------------------------------------+
| AstroVitals Node (Single Static Binary)                                           |
|                                                                                   |
|  +---------------------+        +--------------------+        +----------------+  |
|  |   Chi HTTP Router   | -----> |   Ingest Service   | -----> |   Domain Rule  |  |
|  |  + Middlewares      |        +---------+----------+        |   Engine       |  |
|  +---------------------+                  |                   +-------+--------+  |
|            |                              v                           |           |
|            |                    +--------------------+                v           |
|            |                    |  Transactional DB  |         +--------------+   |
|            |                    | (Telemetry+Outbox) |         | Open/Resolve |   |
|            v                    +---------+----------+         | Alert State  |   |
|  +---------------------+                  |                    +-------+------+   |
|  |   SSE Event Hub     | <----------------+----------------------------+          |
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
- **Operating System:** Linux (Ubuntu 22.04+, Debian 12+, Alpine 3.19+, RHEL 9+), macOS, or Windows
- **Go Version:** Go 1.25+ or 1.26
- **Architecture:** `amd64`, `arm64`, or `armv7`
- **CGO:** NOT required (`CGO_ENABLED=0`). Pure-Go SQLite via `modernc.org/sqlite`.

### 2.2 Compilation
To build a fully static, standalone production binary:
```bash
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o bin/astrovitals cmd/server/main.go
```
The resulting binary has zero dynamic dependencies and can run on any Linux kernel version 3.2+.

### 2.3 Containerization (Docker)
A hardened, unprivileged multi-stage Docker build is provided:
```dockerfile
# Build stage
FROM golang:1.25-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /astrovitals cmd/server/main.go

# Production runtime stage
FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=builder /astrovitals /app/astrovitals
VOLUME ["/data"]
ENV DB_PATH=/data/astrovitals.db
ENV APP_ENV=prod
ENV HTTP_ADDR=:8080
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/app/astrovitals"]
```

Run container:
```bash
docker run -d \
  --name astrovitals \
  --restart always \
  -p 8080:8080 \
  -v astrovitals_data:/data \
  astrovitals:latest
```

---

## 3. Configuration Management

Configuration is loaded from environment variables on startup. The application fails fast if configuration is malformed.

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_ENV` | string | `dev` | `prod` (enables structured JSON logging) or `dev` (console colored log) |
| `HTTP_ADDR` | string | `:8080` | Bind address and port for the HTTP API |
| `DB_PATH` | string | `./data/astrovitals.db` | Absolute or relative filesystem path to the SQLite database |
| `CORS_ORIGINS` | string | `*` | Comma-separated list of allowed origins (e.g. `https://orbit.nasa.gov,http://localhost:3000`) |
| `ALERT_SUSTAIN_SAMPLES` | int | `3` | Number of consecutive anomaly samples required before opening an alert |
| `ALERT_RESOLVE_SAMPLES` | int | `5` | Number of consecutive in-range samples required before auto-resolving an alert |
| `SIM_INTERVAL_MS` | int | `1000` | Telemetry generation tick rate in milliseconds for the simulator |
| `SYNC_REMOTE_URL` | string | `""` | Remote base URL for ground-station synchronization |
| `API_KEY` | string | `""` | Optional shared secret; if set, requires `X-API-Key` on mutation endpoints |

---

## 4. SQLite Storage Engine & Database Pragmas

AstroVitals configures SQLite for maximum write throughput, data safety, and concurrency:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA temp_store=MEMORY;
```

### Storage Considerations:
- **Write-Ahead Logging (WAL):** Allows readers to access the database concurrently without blocking writers, and writers do not block readers.
- **Single Writer Pool:** The write path uses a dedicated connection or serialized write transactions to prevent `SQLITE_BUSY` contention.
- **Embedded Migrations:** Schema migrations are compiled into the binary using `embed` and applied automatically within a transaction upon server start.
- **Disaster Recovery & Backup:** SQLite databases in WAL mode can be hot-backed up safely using standard SQLite backup APIs or by running:
  ```bash
  sqlite3 data/astrovitals.db ".backup data/astrovitals_backup.db"
  ```

---

## 5. Security & Privacy Guardrails

1. **Opaque Error Model:**
   - Client responses never expose database errors, system stack traces, or internal paths.
   - Internal errors return HTTP 500 with a standard generic message: `"Something went wrong."`.
2. **Zero Vital-Sign Leakage in Logs:**
   - Production logs strictly record request metadata (`method`, `path`, `status`, `duration`, `req_id`).
   - Telemetry payload vitals (heart rate, blood pressure, SpO2) are **never** logged under any log level.
3. **Idempotency by Design:**
   - Telemetry samples require a client-generated UUID/ULID (`client_id`). Duplicate submissions return HTTP 202 without creating duplicate rows or re-triggering alert pipelines.
4. **API Key Authentication (Optional):**
   - When `API_KEY` is set, all `POST`, `PATCH`, and `DELETE` endpoints enforce header verification (`X-API-Key`).

---

## 6. Observability & Health Checks

### Liveness Probe
- **Endpoint:** `GET /healthz`
- **Status:** `200 OK`
- **Response:** `{"status":"ok"}`
- **Usage:** Kubernetes or Docker liveness check; executes without touching SQLite.

### Readiness Probe
- **Endpoint:** `GET /readyz`
- **Status:** `200 OK` (or `503 Service Unavailable` if database ping fails)
- **Response:** `{"status":"ok"}`
- **Usage:** Verifies that SQLite connection and file I/O are fully operational.

### Request Correlation
- Every incoming request is assigned or preserves an `X-Request-ID` header.
- This ID is propagated across all log entries, SSE broadcasts, and error responses.

---

## 7. Real-Time Streaming & Client Recovery

- **Protocol:** Server-Sent Events (`text/event-stream`).
- **Heartbeat:** Automatic comment pings (`: ping\n\n`) are broadcast every 15 seconds to keep intermediary proxies, firewalls, and satellite links alive.
- **Backpressure Protection:** In-process subscriber channels are buffered. If a slow client fails to consume events within the buffer capacity, the subscriber is cleanly disconnected without degrading ingest throughput.
- **Fallback:** Clients that cannot sustain SSE streams can seamlessly fall back to polling `GET /api/v1/astronauts` and `GET /api/v1/alerts`.

---

## 8. Offline-to-Ground Synchronization (Outbox Pattern)

1. Telemetry and critical alert events are inserted into the `outbox` table within the same ACID transaction as the primary entity.
2. An autonomous background worker or manual trigger (`POST /api/v1/sync/flush`) batches un-synced outbox rows (`synced_at IS NULL`).
3. Payload is delivered to the ground station endpoint configured via `SYNC_REMOTE_URL`.
4. Upon HTTP 200/204 confirmation from ground, the outbox rows are stamped with `synced_at = unix_now_ms`.
