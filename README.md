# OR-1.0 / AstroVitals

AstroVitals: Offline-first real-time astronaut health monitoring system for the NASA Space Apps Challenge 2026.

## Project Structure

- `AstroVitals.postman_collection.json`: Complete ready-to-import Postman Collection v2.1 covering all endpoints, sample payloads (with/without blood pressure), and SSE streaming.
- `backend/`: FastAPI backend service implementing REST APIs, Server-Sent Events (SSE), SQLite storage (`aiosqlite`), deterministic alert engine, in-process ML inference, dataset importer, and telemetry simulation.
  - See [`backend/README.md`](backend/README.md) for quickstart instructions and curl examples.
  - See [`backend/docs/SPEC.md`](backend/docs/SPEC.md) for full architectural specification.
  - See [`backend/docs/PRODUCTION_GUIDE.md`](backend/docs/PRODUCTION_GUIDE.md) for production operational guide.
  - See [`backend/docs/API.md`](backend/docs/API.md) for API contract reference.

