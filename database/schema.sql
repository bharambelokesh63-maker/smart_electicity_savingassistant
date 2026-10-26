-- Smart Electricity Saving Assistant: SQLite schema
-- All statements are idempotent (IF NOT EXISTS) so init_db() is safe to re-run.

CREATE TABLE IF NOT EXISTS appliances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    category        TEXT    NOT NULL,
    power_w         REAL    NOT NULL CHECK (power_w > 0 AND power_w <= 20000),
    quantity        INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    hours_per_day   REAL    NOT NULL CHECK (hours_per_day > 0 AND hours_per_day <= 24),
    days_per_month  INTEGER NOT NULL CHECK (days_per_month BETWEEN 1 AND 31),
    preferred_start INTEGER NOT NULL CHECK (preferred_start BETWEEN 0 AND 23),
    flexible        INTEGER NOT NULL DEFAULT 0 CHECK (flexible IN (0, 1)),
    min_hours       REAL    NOT NULL DEFAULT 0 CHECK (min_hours >= 0),
    max_hours       REAL             CHECK (max_hours IS NULL OR max_hours <= 24),
    priority        INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 3),
    standby_w       REAL    NOT NULL DEFAULT 0 CHECK (standby_w >= 0 AND standby_w <= 1000),
    window_start    INTEGER NOT NULL DEFAULT 0 CHECK (window_start BETWEEN 0 AND 23),
    window_end      INTEGER NOT NULL DEFAULT 24 CHECK (window_end BETWEEN 1 AND 24),
    is_demo         INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Exactly one row (id = 1) holds the user's tariff assumptions.
CREATE TABLE IF NOT EXISTS tariff_settings (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    base_rate        REAL    NOT NULL DEFAULT 8.0,   -- Rs per kWh
    fixed_charge     REAL    NOT NULL DEFAULT 0.0,   -- Rs per month
    tax_percent      REAL    NOT NULL DEFAULT 0.0,   -- % on (energy + fixed)
    tou_enabled      INTEGER NOT NULL DEFAULT 1,
    peak_start       INTEGER NOT NULL DEFAULT 18,
    peak_end         INTEGER NOT NULL DEFAULT 22,
    peak_multiplier  REAL    NOT NULL DEFAULT 1.25,
    offpeak_start    INTEGER NOT NULL DEFAULT 22,
    offpeak_end      INTEGER NOT NULL DEFAULT 6,
    offpeak_multiplier REAL  NOT NULL DEFAULT 0.80,
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Latest optimized schedule saved by the scheduler.
CREATE TABLE IF NOT EXISTS schedules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    appliance_id   INTEGER NOT NULL REFERENCES appliances(id) ON DELETE CASCADE,
    kind           TEXT    NOT NULL CHECK (kind IN ('original', 'optimized')),
    start_hour     INTEGER NOT NULL CHECK (start_hour BETWEEN 0 AND 23),
    duration_hours INTEGER NOT NULL CHECK (duration_hours BETWEEN 1 AND 24),
    algorithm      TEXT,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Snapshots of the calculator output (user presses "Save snapshot").
CREATE TABLE IF NOT EXISTS usage_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    appliance_count   INTEGER NOT NULL,
    daily_kwh         REAL    NOT NULL,
    monthly_kwh       REAL    NOT NULL,
    tariff_rate       REAL    NOT NULL,
    energy_charge     REAL    NOT NULL,
    estimated_bill    REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    appliance_id       INTEGER REFERENCES appliances(id) ON DELETE SET NULL,
    appliance_name     TEXT    NOT NULL,
    kind               TEXT    NOT NULL,
    issue              TEXT    NOT NULL,
    action             TEXT    NOT NULL,
    reason             TEXT    NOT NULL,
    daily_kwh_saved    REAL    NOT NULL,
    monthly_kwh_saved  REAL    NOT NULL,
    monthly_rs_saved   REAL    NOT NULL,
    feasibility        REAL    NOT NULL,
    score              REAL    NOT NULL,
    assumptions        TEXT    NOT NULL,
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS algorithm_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    algorithm     TEXT    NOT NULL,
    found         INTEGER NOT NULL,
    objective     REAL,
    runtime_ms    REAL    NOT NULL,
    summary       TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedules_appliance ON schedules(appliance_id);
CREATE INDEX IF NOT EXISTS idx_runs_algorithm ON algorithm_runs(algorithm, id);
