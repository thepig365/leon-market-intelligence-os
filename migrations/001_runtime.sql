-- LMIO runtime schema v1.
-- Detailed market evidence stays outside Bayview OS project-memory tables.

CREATE TABLE schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE universe_runs (
    id INTEGER PRIMARY KEY,
    policy_version TEXT NOT NULL,
    input_count INTEGER NOT NULL,
    investable_count INTEGER NOT NULL,
    input_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE screen_runs (
    id INTEGER PRIMARY KEY,
    calculation_version TEXT NOT NULL,
    universe_run_id INTEGER REFERENCES universe_runs(id),
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE valuation_runs (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    calculation_version TEXT NOT NULL,
    input_payload TEXT NOT NULL,
    result_payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE news_events (
    fingerprint TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    report_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE signal_outcomes (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    horizon TEXT NOT NULL,
    return_pct REAL,
    max_adverse_excursion_pct REAL,
    max_favourable_excursion_pct REAL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE telegram_deliveries (
    dedupe_key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    provider_message_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_events (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
