# AstroVitals Backend Specification

NASA Space Apps Challenge 2026 | Go 1.25+ | net/http + chi | SQLite | zap (sugared)

---

## PART 2: PRODUCT CONTEXT

**Goal.** Offline-first, real-time health monitoring for astronauts: capture vitals (HR, ECG summary, SpO2, BP, RR), detect risks, expose data to a dashboard, a 3D heart/body view, an AI assistant, and a lightweight EVA mode.

**Backend's role** (end-to-end flow steps 1 to 3 and the feed for 4 to 6):

1. **Capture**: accept telemetry from the watch (real) or a simulator (or NASA dataset replay).
2. **Process**: validate, normalize, store locally.
3. **Detect**: run rule-based alert rules (deterministic, explainable, offline). The AI team's model results plug in through the assessments endpoint.
4. **Serve**: REST for the dashboard and a live Server-Sent Events (SSE) stream.
5. **Sync later**: an outbox table so data can be pushed to a remote when connectivity returns.

**Team contracts.**

| Consumer | Needs from backend |
|---|---|
| Dashboard (frontend) | REST + SSE, stable JSON, CORS |
| 3D visualization | latest vitals per astronaut (HR drives heartbeat animation) |
| Watch / sensor | `POST /telemetry` (single or batch, idempotent) |
| AI / data team | `POST /assessments` to submit model output; `GET /telemetry` export for training |
| AI assistant | `GET /astronauts/{id}/summary` (compact context for explanations) |

---

## PART 3: ARCHITECTURE AND PACKAGE LAYOUT

```
backend/
├── cmd/
│   ├── server/main.go            # wiring, graceful shutdown
│   └── importer/main.go          # NASA dataset CSV -> replay file / DB
├── internal/
│   ├── config/config.go          # env parsing
│   ├── apperr/apperr.go          # opaque error type + kinds
│   ├── logx/logx.go              # zap sugared logger constructor
│   ├── responses/responses.go    # JSON envelopes (Part 6.0), fixed format
│   ├── domain/                   # pure types + alert rules, no I/O
│   │   ├── telemetry.go
│   │   ├── astronaut.go
│   │   ├── alert.go
│   │   └── rules.go
│   ├── store/                    # SQLite repositories
│   │   ├── db.go                 # open, pragmas, migrate
│   │   ├── migrations/           # 0001_init.sql ... (go:embed)
│   │   ├── astronaut_repo.go
│   │   ├── telemetry_repo.go
│   │   ├── alert_repo.go
│   │   └── outbox_repo.go
│   ├── service/                  # business logic (ingest, alerts, summary)
│   │   ├── ingest.go
│   │   ├── alerts.go
│   │   └── summary.go
│   ├── stream/hub.go             # in-process pub/sub for SSE
│   ├── sim/simulator.go          # scenario-driven fake telemetry
│   └── httpapi/
│       ├── router.go             # chi routes
│       ├── middleware.go         # request id, logging, recover, timeout
│       ├── handlers_*.go
│       ├── dto.go                # request/response structs
│       └── respond.go            # WriteError: apperr -> status + responses.*
├── data/                         # sqlite file + dataset (gitignored)
├── docs/{SPEC.md,API.md,DECISIONS.md,PRODUCTION_GUIDE.md}
├── Makefile
├── Dockerfile
└── go.mod
```

**Dependency direction:** `httpapi -> service -> store`, and `service/store -> domain`. `domain` imports nothing internal. Handlers never touch `database/sql`.

**Concurrency model.**
- `http.Server` with sane timeouts (`ReadHeaderTimeout 5s`, `ReadTimeout 15s`, `IdleTimeout 60s`; no global `WriteTimeout` because SSE is long-lived, so apply timeouts per route with middleware).
- One `*sql.DB` with WAL and `busy_timeout`.
- The `stream.Hub` fans out events to SSE subscribers with buffered channels. Slow clients are dropped, never block ingest.

---

## PART 4: STORAGE (SQLite)

**Pragmas**:
```
journal_mode=WAL; synchronous=NORMAL; foreign_keys=ON; busy_timeout=5000; temp_store=MEMORY
```

**Migrations:** embedded `.sql` files applied in order inside a transaction, tracked in `schema_migrations(version, applied_at)`. Idempotent on startup.

**Schema (`0001_init.sql`):**
```sql
CREATE TABLE astronauts (
  id          TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  mission     TEXT NOT NULL DEFAULT '',
  mode        TEXT NOT NULL DEFAULT 'normal' CHECK (mode IN ('normal','eva')),
  baseline_hr INTEGER NOT NULL DEFAULT 70,
  created_at  INTEGER NOT NULL
);

CREATE TABLE telemetry (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  astronaut_id  TEXT NOT NULL REFERENCES astronauts(id),
  client_id     TEXT NOT NULL,
  recorded_at   INTEGER NOT NULL,
  received_at   INTEGER NOT NULL,
  source        TEXT NOT NULL CHECK (source IN ('watch','simulator','dataset')),
  heart_rate    INTEGER,
  spo2          INTEGER,
  systolic      INTEGER,
  diastolic     INTEGER,
  resp_rate     INTEGER,
  ecg_summary   TEXT,
  stress_index  REAL,
  UNIQUE (astronaut_id, client_id)
);
CREATE INDEX idx_telemetry_astro_time ON telemetry(astronaut_id, recorded_at DESC);

CREATE TABLE alerts (
  id            TEXT PRIMARY KEY,
  astronaut_id  TEXT NOT NULL REFERENCES astronauts(id),
  rule_id       TEXT NOT NULL,
  severity      TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
  title         TEXT NOT NULL,
  message       TEXT NOT NULL,
  metric        TEXT NOT NULL,
  value         REAL NOT NULL,
  threshold     REAL NOT NULL,
  status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','resolved')),
  origin        TEXT NOT NULL DEFAULT 'rules' CHECK (origin IN ('rules','ai','demo')),
  created_at    INTEGER NOT NULL,
  updated_at    INTEGER NOT NULL
);
CREATE INDEX idx_alerts_status ON alerts(status, created_at DESC);
CREATE INDEX idx_alerts_astro ON alerts(astronaut_id, created_at DESC);

CREATE TABLE assessments (
  id            TEXT PRIMARY KEY,
  astronaut_id  TEXT NOT NULL REFERENCES astronauts(id),
  model_version TEXT NOT NULL,
  risk_score    REAL NOT NULL,
  label         TEXT NOT NULL,
  explanation   TEXT NOT NULL DEFAULT '',
  created_at    INTEGER NOT NULL
);

CREATE TABLE outbox (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  entity      TEXT NOT NULL,
  entity_id   TEXT NOT NULL,
  payload     TEXT NOT NULL,
  created_at  INTEGER NOT NULL,
  synced_at   INTEGER
);
CREATE INDEX idx_outbox_pending ON outbox(synced_at) WHERE synced_at IS NULL;
```

---

## PART 5: DOMAIN: ALERT RULES

| rule_id | Metric | Warning | Critical | Notes |
|---|---|---|---|---|
| `hr_high` | heart_rate | > 120 | > 150 | relax by +20 in `eva` mode |
| `hr_low` | heart_rate | < 50 | < 40 | |
| `spo2_low` | spo2 | < 94 | < 90 | |
| `bp_high` | systolic | > 140 | > 170 | |
| `bp_low` | systolic | < 90 | < 80 | |
| `rr_high` | resp_rate | > 22 | > 28 | |
| `rr_low` | resp_rate | < 10 | < 8 | |
| `ecg_irregular` | ecg_summary | "irregular" for 3 consecutive samples | | arrhythmia flag |
| `stress_high` | stress_index | > 0.7 | > 0.9 | |

- **Sustain window:** holds for N=3 consecutive samples before opening alert.
- **Dedup/Cooldown:** at most one open alert per (astronaut_id, rule_id). Escalations update existing alert.
- **Auto-resolve:** metric back in range for 5 consecutive samples resolves alert.
- **Pure function:** `Evaluate(window []Telemetry, mode Mode, openAlerts) []AlertAction`.
- AI assessments raise alert (`origin='ai'`) when `risk_score >= 0.8`.

---

## PART 6: API CONTRACT

Base path `/api/v1`. JSON only. All responses carry `X-Request-ID`.
- 6.0 Fixed responses via `internal/responses` (`SuccessResponse`, `ErrorResponse`, `PaginatedResponse`).
- 6.1 Canonical simulated alert at `GET /api/v1/demo/alert`.
- 6.2 Healthz/Readyz, Astronauts, Mode toggle, Telemetry ingest, History, Summary, Alerts, Assessments, Stream SSE, Sim, Sync.

---

## PART 7: ERROR HANDLING: OPAQUE WRAPPING

Opaque `*apperr.Error`, client safe public messages, mapping Kind to HTTP status codes.

---

## PART 8: LOGGING: MINIMAL, ZAP SUGAR

Minimal logging. Never log vital values, request/response bodies, or per-sample ingest events.

---

## PART 9: CONFIGURATION

- `APP_ENV` (dev/prod)
- `HTTP_ADDR` (:8080)
- `DB_PATH` (./data/astrovitals.db)
- `CORS_ORIGINS` (*)
- `ALERT_SUSTAIN_SAMPLES` (3)
- `ALERT_RESOLVE_SAMPLES` (5)
- `SIM_INTERVAL_MS` (1000)
- `SYNC_REMOTE_URL`
- `API_KEY`
