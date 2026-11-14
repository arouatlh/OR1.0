# AstroVitals API Reference (FastAPI Edition)

Base URL: `http://localhost:8998`
Base Path: `/api/v1`
Automatic OpenAPI Docs: `http://localhost:8998/docs`

All responses carry an `X-Request-ID` header.

---

## Response Envelopes

### Success Envelope
```json
{
  "message": "Success",
  "status_code": 200,
  "data": { ... }
}
```

### Paginated Envelope
```json
{
  "message": "Success",
  "status_code": 200,
  "count": 20,
  "data": [ ... ]
}
```

### Error Envelope
```json
{
  "message": "validation failed: samples.0.spo2 must be between 50 and 100",
  "status_code": 422
}
```

---

## Endpoints

### 1. Health Probes
- `GET /healthz`: Liveness probe (`{"status":"ok"}`).
- `GET /readyz`: Readiness probe (`{"status":"ok", "ml_loaded": true}`).

### 2. Demo Alert (Milestone 1)
- `GET /api/v1/demo/alert`: Canonical simulated alert JSON (Part 6.1).

### 3. Astronauts
- `GET /api/v1/astronauts`: List all astronauts with latest vitals, open alerts count, and status (`nominal`, `warning`, `critical`).
- `GET /api/v1/astronauts/{id}`: Detailed astronaut profile with latest vitals and assessment.
- `PATCH /api/v1/astronauts/{id}/mode`: Body `{"mode":"eva"}` toggles EVA mode.
- `GET /api/v1/astronauts/{id}/summary`: Compact summary for AI assistant (profile, latest sample, 5-min stats, active open alerts, latest assessment).
- `GET /api/v1/astronauts/{id}/assessments`: Paginated ML assessment history.

### 4. Telemetry
- `POST /api/v1/telemetry`: Batch ingest telemetry samples (idempotent via `client_id`). Returns `202 Accepted`.
- `GET /api/v1/astronauts/{id}/telemetry`: Paginated telemetry history (`from`, `to`, `offset`, `limit`, `order`).
- `GET /api/v1/telemetry/export`: Telemetry export for AI/model training.

### 5. Alerts
- `GET /api/v1/alerts`: Paginated alerts list (`status`, `severity`, `astronaut_id`, `offset`, `limit`).
- `POST /api/v1/alerts/{id}/ack`: Acknowledge an open alert.

### 6. AI Assessments
- `POST /api/v1/assessments`: Submit external model assessment score (risk_score >= 0.8 triggers AI alert).

### 7. Real-Time Stream (SSE)
- `GET /api/v1/stream`: Server-Sent Events live stream (`?astronaut_id=...`). 15-second heartbeat comment `: ping\n\n`.
  - `event: telemetry`
  - `event: alert`
  - `event: alert_update`
  - `event: assessment`

### 8. Simulator
- `POST /api/v1/simulate/start`: Start simulation `{"scenario":"normal|tachycardia|hypoxia|arrhythmia", "astronaut_id":"astro-a"}`.
- `POST /api/v1/simulate/stop`: Stop active simulation.

### 9. Outbox & Sync
- `GET /api/v1/sync/status`: Pending outbox queue count and last sync timestamp.
- `POST /api/v1/sync/flush`: Push pending outbox records to `SYNC_REMOTE_URL`.
