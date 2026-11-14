# AstroVitals API Reference (v1)

Base URL: `http://localhost:8080` (or configured `HTTP_ADDR`)
Base Path: `/api/v1`
Protocol: HTTP / JSON + Server-Sent Events

All requests and responses carry an `X-Request-ID` correlation header.

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
  "message": "validation failed: samples[0].spo2 must be between 50 and 100",
  "status_code": 422
}
```

---

## Endpoints

### 1. Health Probes (Non-enveloped)
- `GET /healthz`: Liveness probe (`{"status":"ok"}`)
- `GET /readyz`: Readiness probe (checks SQLite connection)

### 2. Demo Alert (Milestone 1)
- `GET /api/v1/demo/alert`: Canonical simulated critical alert.

### 3. Astronauts
- `GET /api/v1/astronauts`: List all astronauts with current vital metrics, open alerts count, and status (`nominal`, `warning`, `critical`).
- `GET /api/v1/astronauts/{id}`: Detailed astronaut profile with latest vitals.
- `PATCH /api/v1/astronauts/{id}/mode`: Toggle astronaut mode (`normal` or `eva`). Body: `{"mode": "eva"}`.
- `GET /api/v1/astronauts/{id}/summary`: Compact clinical summary for AI assistants (profile, latest sample, 5-minute rolling statistics, active open alerts).

### 4. Telemetry
- `POST /api/v1/telemetry`: Batch ingest telemetry samples (idempotent via client_id).
  - Body:
    ```json
    {
      "astronaut_id": "astro-a",
      "samples": [
        {
          "client_id": "watch-01-001",
          "recorded_at": "2026-11-14T10:30:00Z",
          "source": "watch",
          "heart_rate": 72,
          "spo2": 98,
          "systolic": 118,
          "diastolic": 76,
          "resp_rate": 14,
          "ecg_summary": "sinus",
          "stress_index": 0.2
        }
      ]
    }
    ```
  - Response: `202 Accepted` (`{"accepted": 1, "duplicates": 0, "alerts_opened": 0}`)
- `GET /api/v1/astronauts/{id}/telemetry`: Paginated telemetry history. Query parameters: `from`, `to` (RFC 3339), `offset`, `limit` (max 500), `order` (`ASC` or `DESC`).
- `GET /api/v1/telemetry`: Export telemetry for AI / model training.

### 5. Alerts
- `GET /api/v1/alerts`: Paginated alerts list. Query filters: `status`, `severity`, `astronaut_id`, `offset`, `limit`.
- `POST /api/v1/alerts/{id}/ack`: Acknowledge an open alert. Returns 409 Conflict if already resolved.

### 6. AI Assessments
- `POST /api/v1/assessments`: Submit AI anomaly/risk assessment score. Body:
  ```json
  {
    "astronaut_id": "astro-a",
    "model_version": "v1.0-ecg-net",
    "risk_score": 0.88,
    "label": "arrhythmia_risk",
    "explanation": "Elevated ST elevation pattern detected"
  }
  ```
  Automatically triggers an alert if `risk_score >= 0.8`.

### 7. Real-Time SSE Stream
- `GET /api/v1/stream`: Server-Sent Events stream. Optional filter: `?astronaut_id=astro-a`.
  - Heartbeat comment `: ping\n\n` emitted every 15s.
  - Events:
    - `event: telemetry` -> latest telemetry sample
    - `event: alert` -> newly opened or escalated alert
    - `event: alert_update` -> alert resolved or acknowledged

### 8. Simulator
- `POST /api/v1/simulate/start`: Start built-in telemetry simulation. Body:
  `{"scenario": "normal|tachycardia|hypoxia|arrhythmia", "astronaut_id": "astro-a"}`
- `POST /api/v1/simulate/stop`: Stop active simulation.

### 9. Outbox & Sync
- `GET /api/v1/sync/status`: Pending outbox queue count and last sync timestamp.
- `POST /api/v1/sync/flush`: Push pending outbox records to `SYNC_REMOTE_URL`.
