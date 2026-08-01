"""Versioned SQLite persistence for local LMIO runtime evidence."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 7
MIGRATION = """
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS universe_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_version TEXT NOT NULL,
    input_count INTEGER NOT NULL,
    investable_count INTEGER NOT NULL,
    input_hash TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS screen_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calculation_version TEXT NOT NULL,
    universe_run_id INTEGER,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (universe_run_id) REFERENCES universe_runs(id)
);
CREATE TABLE IF NOT EXISTS valuation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    calculation_version TEXT NOT NULL,
    input_payload TEXT NOT NULL,
    result_payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS news_events (
    fingerprint TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS synthetic_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_type TEXT NOT NULL,
    provenance TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    signal_date TEXT NOT NULL,
    horizon TEXT NOT NULL,
    return_pct REAL,
    max_adverse_excursion_pct REAL,
    max_favourable_excursion_pct REAL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS telegram_deliveries (
    dedupe_key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    provider_message_id TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS research_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    model_version TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS conditional_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    state TEXT NOT NULL,
    version TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS provider_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    state TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
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
CREATE TABLE IF NOT EXISTS symbol_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS market_prices_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS market_prices_intraday (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS market_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS fundamentals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS financial_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS earnings_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS earnings_estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS earnings_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS news_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS news_symbol_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sec_filings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS institutional_managers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS institutional_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS insider_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS short_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS options_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS social_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS market_regimes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS screen_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS screen_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS stock_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS candidate_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS valuation_assumptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS valuation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS signal_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS trade_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS paper_trade_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, source TEXT, source_url TEXT,
    observed_at TEXT, schema_version TEXT, payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ingestion_dedup (
    fingerprint TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class RuntimeStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connection() as connection:
            connection.executescript(MIGRATION)
            telegram_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(telegram_deliveries)").fetchall()
            }
            if "attempt_count" not in telegram_columns:
                connection.execute(
                    """
                    ALTER TABLE telegram_deliveries
                    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0
                    """
                )
            if "last_attempt_at" not in telegram_columns:
                connection.execute(
                    "ALTER TABLE telegram_deliveries ADD COLUMN last_attempt_at TEXT"
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO schema_versions(version)
                SELECT 4
                WHERE EXISTS (
                    SELECT 1 FROM schema_versions WHERE version = 3
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO schema_versions(version)
                SELECT 5
                WHERE EXISTS (
                    SELECT 1 FROM schema_versions WHERE version = 4
                )
                """
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO schema_versions(version)
                SELECT 6
                WHERE EXISTS (
                    SELECT 1 FROM schema_versions WHERE version = 5
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_versions(version) VALUES (?)",
                (SCHEMA_VERSION,),
            )

    def integrity_check(self) -> list[str]:
        """Return SQLite integrity findings; a healthy store returns only ``ok``."""

        with self.connection() as connection:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
        return [str(row[0]) for row in rows]

    def schema_versions(self) -> list[int]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT version FROM schema_versions ORDER BY version"
            ).fetchall()
        return [int(row[0]) for row in rows]

    def backup_to(self, destination: str | Path) -> dict[str, Any]:
        """Create and verify a non-destructive, consistent SQLite backup."""

        if str(self.path) == ":memory:":
            raise ValueError("in-memory stores cannot be backed up")
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        target = Path(destination)
        if target.resolve() == self.path.resolve():
            raise ValueError("backup destination must differ from the active store")
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        source = sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True)
        backup = sqlite3.connect(target)
        try:
            source.backup(backup)
        finally:
            backup.close()
            source.close()
        verified = RuntimeStore(target)
        findings = verified.integrity_check()
        if findings != ["ok"]:
            raise RuntimeError(f"backup integrity check failed: {findings}")
        digest = sha256(target.read_bytes()).hexdigest()
        return {
            "source": str(self.path),
            "backup": str(target),
            "sha256": digest,
            "bytes": target.stat().st_size,
            "schema_versions": verified.schema_versions(),
            "counts": verified.counts(),
            "integrity": findings,
        }

    def append_json(self, table: str, columns: dict[str, Any]) -> int:
        allowed = {
            "universe_runs",
            "screen_runs",
            "valuation_runs",
            "reports",
            "signal_outcomes",
            "system_events",
            "research_packs",
            "conditional_plans",
            "provider_health",
            "provider_snapshots",
            "candidate_transitions",
            "trade_plan_transitions",
            "ownership_events",
            "signals",
            "user_feedback",
            "strategy_performance",
            "watchlists",
            "watchlist_members",
            "synthetic_records",
        }
        if table not in allowed:
            raise ValueError(f"unsupported append table: {table}")
        keys = list(columns)
        placeholders = ", ".join("?" for _ in keys)
        values = [
            (
                json.dumps(value, sort_keys=True, default=str)
                if isinstance(value, dict | list)
                else value
            )
            for value in columns.values()
        ]
        with self.connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})",
                values,
            )
            return int(cursor.lastrowid)

    def latest_json(self, table: str) -> dict[str, Any] | None:
        allowed = {"universe_runs", "screen_runs", "reports"}
        if table not in allowed:
            raise ValueError(f"unsupported latest table: {table}")
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT payload FROM {table} ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def latest_provider_health(self) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT provider, state, payload, created_at
                FROM provider_health
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        return item

    def history_json(self, table: str, limit: int = 50) -> list[dict[str, Any]]:
        allowed = {
            "universe_runs",
            "screen_runs",
            "valuation_runs",
            "reports",
            "research_packs",
            "conditional_plans",
            "provider_health",
            "provider_snapshots",
            "candidate_transitions",
            "trade_plan_transitions",
            "ownership_events",
            "signals",
            "user_feedback",
            "strategy_performance",
            "watchlists",
            "watchlist_members",
            "synthetic_records",
        }
        if table not in allowed:
            raise ValueError(f"unsupported history table: {table}")
        bounded_limit = max(1, min(limit, 200))
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?",
                (bounded_limit,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in ("payload", "input_payload", "result_payload"):
                if key in item:
                    item[key] = json.loads(item[key])
            result.append(item)
        return result

    def counts(self) -> dict[str, int]:
        tables = (
            "universe_runs",
            "screen_runs",
            "valuation_runs",
            "news_events",
            "reports",
            "signal_outcomes",
            "telegram_deliveries",
            "system_events",
            "research_packs",
            "conditional_plans",
            "provider_health",
            "symbols",
            "provider_snapshots",
            "candidate_transitions",
            "trade_plan_transitions",
            "ownership_events",
            "signals",
            "user_feedback",
            "strategy_performance",
            "watchlists",
            "watchlist_members",
            "synthetic_records",
        )
        with self.connection() as connection:
            return {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in tables
            }

    def put_news_event(self, fingerprint: str, payload: dict[str, Any]) -> bool:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO news_events(fingerprint, payload)
                VALUES (?, ?)
                """,
                (fingerprint, json.dumps(payload, sort_keys=True, default=str)),
            )
            return cursor.rowcount == 1

    def put_ownership_event(
        self,
        fingerprint: str,
        *,
        symbol: str,
        event_type: str,
        source_url: str,
        payload: dict[str, Any],
    ) -> bool:
        """Atomically persist one structured ownership record exactly once."""

        with self.connection() as connection:
            marker = connection.execute(
                """
                INSERT OR IGNORE INTO ingestion_dedup(fingerprint, record_type)
                VALUES (?, 'ownership_event')
                """,
                (fingerprint,),
            )
            if marker.rowcount != 1:
                return False
            connection.execute(
                """
                INSERT INTO ownership_events(symbol, event_type, source_url, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    symbol,
                    event_type,
                    source_url,
                    json.dumps(payload, sort_keys=True, default=str),
                ),
            )
            return True

    def put_provider_snapshot(
        self,
        fingerprint: str,
        *,
        provider: str,
        symbol: str,
        company: str,
        observed_at: str,
        payload: dict[str, Any],
    ) -> bool:
        """Atomically persist one normalised provider snapshot exactly once."""

        with self.connection() as connection:
            marker = connection.execute(
                """
                INSERT OR IGNORE INTO ingestion_dedup(fingerprint, record_type)
                VALUES (?, 'provider_snapshot')
                """,
                (fingerprint,),
            )
            if marker.rowcount != 1:
                return False
            connection.execute(
                """
                INSERT INTO provider_snapshots(provider, symbol, observed_at, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    provider,
                    symbol,
                    observed_at,
                    json.dumps(payload, sort_keys=True, default=str),
                ),
            )
            connection.execute(
                """
                INSERT INTO symbols(symbol, company, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    company = excluded.company,
                    payload = excluded.payload,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    symbol,
                    company,
                    json.dumps(
                        {"source": payload.get("source"), "observed_at": observed_at},
                        sort_keys=True,
                        default=str,
                    ),
                ),
            )
            return True

    def has_ingestion_fingerprint(self, fingerprint: str) -> bool:
        """Return whether a bounded ingestion unit completed successfully."""

        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM ingestion_dedup WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return row is not None

    def mark_ingestion_fingerprint(self, fingerprint: str, record_type: str) -> bool:
        """Mark an ingestion unit complete after its records are persisted."""

        with self.connection() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO ingestion_dedup(fingerprint, record_type)
                VALUES (?, ?)
                """,
                (fingerprint, record_type),
            )
            return cursor.rowcount == 1

    def news_payloads(self, limit: int = 500) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(limit, 2000))
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM news_events ORDER BY created_at DESC LIMIT ?",
                (bounded_limit,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def news_event(self, fingerprint: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM news_events WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return json.loads(row["payload"]) if row is not None else None

    def telegram_delivery(self, key: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT status, attempt_count
                FROM telegram_deliveries
                WHERE dedupe_key = ?
                """,
                (key,),
            ).fetchone()
        return dict(row) if row is not None else None

    def sent_telegram_count_since(self, since: datetime) -> int:
        value = since.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM telegram_deliveries
                WHERE status = 'sent' AND created_at >= ?
                """,
                (value,),
            ).fetchone()
        return int(row[0])

    def upsert_telegram_delivery(
        self,
        *,
        key: str,
        status: str,
        payload: dict[str, Any],
        provider_message_id: str | None,
        attempt_increment: int,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO telegram_deliveries
                    (
                        dedupe_key,
                        status,
                        payload,
                        provider_message_id,
                        attempt_count,
                        last_attempt_at
                    )
                VALUES (
                    ?, ?, ?, ?, ?,
                    CASE WHEN ? > 0 THEN CURRENT_TIMESTAMP ELSE NULL END
                )
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    status = excluded.status,
                    payload = excluded.payload,
                    provider_message_id = excluded.provider_message_id,
                    attempt_count = (
                        telegram_deliveries.attempt_count + excluded.attempt_count
                    ),
                    last_attempt_at = CASE
                        WHEN excluded.attempt_count > 0 THEN CURRENT_TIMESTAMP
                        ELSE telegram_deliveries.last_attempt_at
                    END
                """,
                (
                    key,
                    status,
                    json.dumps(payload, ensure_ascii=False),
                    provider_message_id,
                    attempt_increment,
                    attempt_increment,
                ),
            )
