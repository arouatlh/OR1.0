CREATE TABLE IF NOT EXISTS schema_migrations (
  version     TEXT PRIMARY KEY,
  applied_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS astronauts (
  id          TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  mission     TEXT NOT NULL DEFAULT '',
  mode        TEXT NOT NULL DEFAULT 'normal' CHECK (mode IN ('normal','eva')),
  baseline_hr INTEGER NOT NULL DEFAULT 70,
  created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
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
CREATE INDEX IF NOT EXISTS idx_telemetry_astro_time ON telemetry(astronaut_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
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
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_astro ON alerts(astronaut_id, created_at DESC);

CREATE TABLE IF NOT EXISTS assessments (
  id            TEXT PRIMARY KEY,
  astronaut_id  TEXT NOT NULL REFERENCES astronauts(id),
  model_version TEXT NOT NULL,
  risk_score    REAL NOT NULL,
  label         TEXT NOT NULL,
  explanation   TEXT NOT NULL DEFAULT '',
  created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  entity      TEXT NOT NULL,
  entity_id   TEXT NOT NULL,
  payload     TEXT NOT NULL,
  created_at  INTEGER NOT NULL,
  synced_at   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(synced_at) WHERE synced_at IS NULL;
