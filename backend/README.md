# AstroVitals Backend (FastAPI Edition)

> **NASA Space Apps Challenge 2026**  
> **DISCLAIMER:** AstroVitals is an engineering prototype designed for simulated mission telemetry and hackathon demonstration. It is **NOT** a certified medical device and thresholds are demo heuristics.

AstroVitals is a resilient, offline-first astronaut telemetry ingestion and real-time vital monitoring backend built with **Python 3.12+, FastAPI, Uvicorn, aiosqlite, structlog, and in-process ML inference**.

---

## Quickstart in 3 Commands

```bash
cd backend
uv sync
make run
```
The server will start on `http://localhost:8998` with pre-seeded astronauts (`astro-a`, `astro-b`, `astro-c`).  
Interactive OpenAPI documentation is available at `http://localhost:8998/docs`.

---

## Canonical Alert (First Milestone)

Fetch the canonical simulated alert JSON formatted specifically for the frontend UI:

```bash
curl -s http://localhost:8998/api/v1/demo/alert | jq
```

---

## Curl Cookbook

### 1. Check Health & Readiness
```bash
# Liveness
curl -i http://localhost:8998/healthz

# Readiness (verifies DB and in-process ML status)
curl -i http://localhost:8998/readyz
```

### 2. Ingest Telemetry
```bash
curl -X POST http://localhost:8998/api/v1/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "astronaut_id": "astro-a",
    "samples": [
      {
        "client_id": "watch-sample-101",
        "recorded_at": "2026-11-14T10:30:00Z",
        "source": "watch",
        "heart_rate": 74,
        "spo2": 98,
        "systolic": 118,
        "diastolic": 76,
        "resp_rate": 14,
        "ecg_summary": "sinus",
        "stress_index": 0.2
      }
    ]
  }'
```

### 3. Stream Real-Time Events (SSE)
```bash
curl -N http://localhost:8998/api/v1/stream?astronaut_id=astro-a
```

### 4. Toggle EVA Mode
```bash
curl -X PATCH http://localhost:8998/api/v1/astronauts/astro-a/mode \
  -H "Content-Type: application/json" \
  -d '{"mode":"eva"}'
```

### 5. Start Telemetry Simulator
```bash
curl -X POST http://localhost:8998/api/v1/simulate/start \
  -H "Content-Type: application/json" \
  -d '{"scenario":"tachycardia","astronaut_id":"astro-a"}'
```

### 6. Stop Simulator
```bash
curl -X POST http://localhost:8998/api/v1/simulate/stop
```

### 7. AI Risk Assessment Ingest
```bash
curl -X POST http://localhost:8998/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d '{
    "astronaut_id": "astro-a",
    "model_version": "v1.0",
    "risk_score": 0.89,
    "label": "arrhythmia_risk",
    "explanation": "Elevated ST-segment variance"
  }'
```

### 8. Fetch AI Assistant Clinical Summary
```bash
curl -s http://localhost:8998/api/v1/astronauts/astro-a/summary | jq
```

---

## Running Tests & Static Checks

```bash
# Run unit & integration tests
uv run pytest -q

# Run ruff linter
uv run ruff check .
```

---

## Documentation & Postman

- **Postman Collection:** [`AstroVitals.postman_collection.json`](docs/AstroVitals.postman_collection.json) (or root [`AstroVitals.postman_collection.json`](../AstroVitals.postman_collection.json))
- [Backend Specification](docs/SPEC.md)
- [Production & Operational Guide](docs/PRODUCTION_GUIDE.md)
- [API Reference](docs/API.md)
- [Architectural Decisions (ADR)](docs/DECISIONS.md)
