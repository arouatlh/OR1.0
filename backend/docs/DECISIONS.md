# AstroVitals Architectural Decision Records (ADR)

## ADR-001: Go Toolchain & Error Handling
- **Context:** The specification references Go 1.26 with fallback notes for `errors.AsType` in Part 15.
- **Decision:** Implemented `errors.As` for kind unwrapping in `internal/apperr/apperr.go`. This guarantees identical behavior across Go 1.25 and 1.26 toolchains while maintaining strict opaque encapsulation.

## ADR-002: Storage Engine & Concurrency
- **Context:** The system must function entirely offline with zero network dependencies.
- **Decision:** Used pure-Go SQLite (`modernc.org/sqlite`) without CGO. Configured WAL journal mode, 5000ms busy timeout, and a single writer pool (`SetMaxOpenConns(1)`) to eliminate write contention and `SQLITE_BUSY` errors.

## ADR-003: Pure Domain Rule Evaluator
- **Context:** Astronaut health alert rules require sustain windows, deduplication, escalation, and auto-resolution without flapping.
- **Decision:** `domain.Evaluate` was implemented as a pure function with zero I/O:
  `Evaluate(astronautID, window, mode, openAlerts, sustainCount, resolveCount, evalTime) []AlertAction`.
  This allows exhaustive unit testing of clinical heuristics and state transitions.

## ADR-004: Opaque Error Boundary
- **Context:** Security and API stability require that database details, table names, and system paths never leak to API consumers.
- **Decision:** All JSON error responses are channeled exclusively through `httpapi.Responder.WriteError`, which maps internal kinds to HTTP codes, logs the full internal error chain once at the HTTP boundary, and returns only pre-vetted safe messages (e.g. `"Something went wrong."` for 500s).

## ADR-005: Event-Driven Real-Time Streaming
- **Context:** The dashboard and 3D visualization require immediate telemetry and alert feeds.
- **Decision:** Implemented an in-process pub/sub `stream.Hub` using Server-Sent Events (SSE) with non-blocking channel fanout and 15-second heartbeat pings. Slow or unresponsive subscribers are dropped without impeding telemetry ingestion throughput.
