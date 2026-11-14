# AstroVitals Backend Specification (FastAPI Edition)

NASA Space Apps Challenge 2026 | Python 3.12+ | FastAPI | aiosqlite | structlog

---

## PART 2: PRODUCT CONTEXT

**Goal.** Offline-first, real-time health monitoring for astronauts: capture vitals (HR, ECG summary, SpO2, BP, RR), detect risks, expose data to a dashboard, a 3D heart/body view, an AI assistant, and a lightweight EVA mode.

**Backend's role:**
1. **Capture**: accept telemetry from the watch, a simulator, or a NASA dataset replay.
2. **Process**: validate, normalize, store locally.
3. **Detect**: deterministic rules (always on, explainable) **plus** the ML predictor (in-process, optional).
4. **Serve**: REST for the dashboard and a live Server-Sent Events (SSE) stream.
5. **Sync later**: an outbox table so data can be pushed to a remote when connectivity returns.

**Why FastAPI here.** The ML model, feature code, and dataset tooling are Python. In-process means no extra HTTP hop, no second deployment, a shared schema (Pydantic), and the model runs offline on the same machine. FastAPI also gives automatic OpenAPI docs at `/docs` for the frontend team.

---

## PART 3: ARCHITECTURE AND PACKAGE LAYOUT

```
backend/
├── pyproject.toml                  # uv; optional group "ml"
├── app/
│   ├── main.py                     # create_app(), lifespan (startup/shutdown)
│   ├── config.py                   # pydantic-settings
│   ├── errors.py                   # opaque AppError + Kind
│   ├── logging.py                  # structlog setup
│   ├── responses.py                # fixed JSON envelopes (Part 6.0)
│   ├── domain/
│   │   ├── models.py               # dataclasses/enums: Sample, Alert, Mode, Severity
│   │   └── rules.py                # pure alert rules (Part 5)
│   ├── db/
│   │   ├── connection.py           # open, pragmas, write lock, migrate
│   │   ├── migrations/0001_init.sql
│   │   ├── astronauts.py           # repositories (plain functions/classes)
│   │   ├── telemetry.py
│   │   ├── alerts.py
│   │   ├── assessments.py
│   │   └── outbox.py
│   ├── services/
│   │   ├── ingest.py               # validate -> store -> rules -> ML -> publish
│   │   ├── alerts.py
│   │   ├── summary.py
│   │   └── inference.py            # runs Predictor off the event loop
│   ├── ml/
│   │   ├── predictor.py            # Predictor Protocol + NullPredictor
│   │   ├── features.py             # window -> feature vector (ML team)
│   │   ├── model.py                # ML team's real predictor
│   │   └── artifacts/              # model files (gitignored or LFS)
│   ├── stream/hub.py               # in-process pub/sub for SSE
│   ├── sim/simulator.py            # scenario-driven fake telemetry
│   └── api/
│       ├── router.py               # mounts routers under /api/v1
│       ├── schemas.py              # Pydantic request/response models
│       ├── routes_*.py             # astronauts, telemetry, alerts, stream, sim, sync, assessments
│       ├── middleware.py           # pure ASGI: request id + request log
│       └── handlers.py             # exception handlers -> responses.py
├── scripts/import_dataset.py       # NASA dataset CSV -> DB / replay JSONL
├── tests/
├── data/                           # sqlite file + dataset (gitignored)
├── docs/{SPEC.md,API.md,DECISIONS.md,PRODUCTION_GUIDE.md}
├── Dockerfile
└── Makefile
```

---

## PART 4: STORAGE (SQLite)

- Pragmas: `journal_mode=WAL; synchronous=NORMAL; foreign_keys=ON; busy_timeout=5000; temp_store=MEMORY`.
- Migrations: `app/db/migrations/0001_init.sql` tracked in `schema_migrations`.
- Concurrency: `write_tx()` async context manager holding an `asyncio.Lock` running `BEGIN IMMEDIATE`.
- Seed 3 astronauts (`astro-a`, `astro-b`, `astro-c`) at startup if table is empty.

---

## PART 5: DOMAIN: ALERT RULES

- Deterministic rules: `hr_high`, `hr_low`, `spo2_low`, `bp_high`, `bp_low`, `rr_high`, `rr_low`, `ecg_irregular`, `stress_high`.
- Sustain window N=3 samples.
- Dedup & escalation: at most one open alert per (astronaut_id, rule_id); escalations update existing alert.
- Auto-resolve: 5 consecutive in-range samples resolves alert.
- EVA mode: relaxes `hr_high` warning threshold to 140 bpm, critical to 170 bpm.

---

## PART 6: API CONTRACT

- All responses carry `X-Request-ID`.
- Fixed JSON envelopes via `app/responses.py` (`SuccessResponse`, `ErrorResponse`, `PaginatedResponse`).
- Canonical simulated alert endpoint: `GET /api/v1/demo/alert`.
- Liveness `/healthz`, readiness `/readyz`.
- Telemetry batch ingest: `POST /api/v1/telemetry` (returns 202 Accepted, idempotent).
- SSE Stream: `GET /api/v1/stream` with 15s heartbeats.
