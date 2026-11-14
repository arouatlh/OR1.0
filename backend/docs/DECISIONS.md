# AstroVitals Architectural Decision Records (FastAPI Edition)

## ADR-001: Migration to FastAPI & In-Process ML Architecture
- **Context:** The machine learning anomaly model, feature extraction pipelines, and dataset ingestion tooling are written in Python.
- **Decision:** Ported the backend from Go to FastAPI (Python 3.12+). This brings ML inference in-process with zero HTTP hop, eliminates multi-service deployment boundaries, allows shared Pydantic validation schemas, and delivers interactive OpenAPI documentation at `/docs`.

## ADR-002: In-Process Thread Isolation for CPU-Bound ML
- **Context:** Heavy model inference on the asyncio event loop would degrade REST response times and starve SSE streaming.
- **Decision:** Executed model inference using `anyio.to_thread.run_sync` wrapped in an explicit `asyncio.timeout(0.5)` with an in-flight guard to run at most one inference task per astronaut at a time.

## ADR-003: Single Uvicorn Worker Model
- **Context:** AstroVitals maintains in-process pub/sub SSE subscriber queues, an active simulator task, and an SQLite immediate write transaction lock.
- **Decision:** Strictly enforced running Uvicorn with a single worker process (`--workers 1`). Multi-worker deployments would partition SSE clients from real-time events.

## ADR-004: Pure ASGI Middleware for Request Tracking & Logging
- **Context:** Standard Starlette `BaseHTTPMiddleware` buffers responses and can interfere with long-lived streaming responses (SSE).
- **Decision:** Implemented `ASGIMiddleware` as a pure ASGI callable for correlation ID injection (`X-Request-ID`), payload size enforcement, and minimal request duration logging.

## ADR-005: Pure Domain Alert Evaluation Engine
- **Context:** Alert rules require sustain windows, deduplication, escalation, and auto-resolution without flapping.
- **Decision:** Preserved `evaluate` as a pure function with zero I/O in `app/domain/rules.py` for deterministic table-driven testing.
