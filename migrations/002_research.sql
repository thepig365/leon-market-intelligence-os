-- LMIO runtime schema v2: versioned research and health records.

CREATE TABLE research_packs (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    model_version TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE conditional_plans (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    state TEXT NOT NULL,
    version TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE provider_health (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    state TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
