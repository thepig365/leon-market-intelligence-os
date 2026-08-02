CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS provider_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    symbol TEXT,
    observed_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS candidate_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trade_plan_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    previous_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ownership_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_url TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    state TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS strategy_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,
    horizon TEXT NOT NULL,
    regime TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS watchlist_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(watchlist_id, symbol),
    FOREIGN KEY (watchlist_id) REFERENCES watchlists(id)
);

-- The remaining governing Master Spec entities use a versioned evidence
-- envelope. Deferred tables exist for schema compatibility but are not active.
CREATE TABLE IF NOT EXISTS symbol_classifications (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS market_prices_daily (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS market_prices_intraday (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS market_indicators (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS fundamentals (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS financial_statements (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS earnings_events (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS earnings_estimates (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS earnings_revisions (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS news_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS news_symbol_links (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS sec_filings (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS institutional_managers (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS institutional_holdings (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS insider_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS short_interest (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS options_flow (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS social_mentions (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS market_regimes (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS screen_definitions (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS screen_results (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS stock_candidates (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS candidate_evidence (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS valuation_assumptions (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS valuation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS signal_scores (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS trade_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT, observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
