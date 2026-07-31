-- LMIO runtime schema v4: generic deduplication keys for structured ingestion.

CREATE TABLE IF NOT EXISTS ingestion_dedup (
    fingerprint TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
