import sqlite3
from pathlib import Path

import pytest

from lmio.store import RuntimeStore


def test_backup_is_consistent_verified_and_non_destructive(tmp_path: Path) -> None:
    active_path = tmp_path / "active.sqlite3"
    backup_path = tmp_path / "backups" / "lmio.sqlite3"
    store = RuntimeStore(active_path)
    store.migrate()
    store.append_json(
        "reports",
        {
            "report_type": "test",
            "payload": {"message": "evidence"},
        },
    )

    manifest = store.backup_to(backup_path)

    assert active_path.exists()
    assert backup_path.exists()
    assert manifest["integrity"] == ["ok"]
    assert manifest["schema_versions"] == [12]
    assert manifest["counts"] == store.counts()
    assert manifest["sha256"]
    assert manifest["bytes"] > 0
    assert store.connectivity_check()["status"] == "ok"
    assert store.schema_check()["schema_versions"] == [12]
    assert store.rls_check()["status"] == "not_applicable"
    assert store.record_count_check()["counts"]["reports"] == 1
    assert store.referential_integrity_check() == {"status": "ok", "findings": []}


def test_backup_refuses_overwrite_and_active_store_destination(tmp_path: Path) -> None:
    active_path = tmp_path / "active.sqlite3"
    store = RuntimeStore(active_path)
    store.migrate()

    with pytest.raises(ValueError, match="must differ"):
        store.backup_to(active_path)

    backup_path = tmp_path / "backup.sqlite3"
    store.backup_to(backup_path)
    with pytest.raises(FileExistsError):
        store.backup_to(backup_path)


def test_backup_refuses_missing_or_memory_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        RuntimeStore(tmp_path / "missing.sqlite3").backup_to(tmp_path / "backup.sqlite3")
    with pytest.raises(ValueError, match="in-memory"):
        RuntimeStore(":memory:").backup_to(tmp_path / "backup.sqlite3")


def test_schema_six_upgrades_an_existing_schema_three_store(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_versions (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO schema_versions(version) VALUES (3);
        """
    )
    connection.close()

    store = RuntimeStore(path)
    store.migrate()

    assert store.schema_versions() == [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    with store.connection() as upgraded:
        row = upgraded.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ingestion_dedup'"
        ).fetchone()
    assert row is not None


def test_schema_five_adds_telegram_retry_fields_to_schema_four(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy-v4.sqlite3"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_versions (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO schema_versions(version) VALUES (4);
        CREATE TABLE telegram_deliveries (
            dedupe_key TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            payload TEXT NOT NULL,
            provider_message_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO telegram_deliveries(dedupe_key, status, payload)
        VALUES ('legacy', 'failed', '{}');
        """
    )
    connection.close()

    store = RuntimeStore(path)
    store.migrate()

    assert store.schema_versions() == [4, 5, 6, 7, 8, 9, 10, 11, 12]
    with store.connection() as upgraded:
        row = upgraded.execute(
            """
            SELECT attempt_count, last_attempt_at, claim_token, claimed_at
            FROM telegram_deliveries
            WHERE dedupe_key = 'legacy'
            """
        ).fetchone()
    assert row is not None
    assert row["attempt_count"] == 0
    assert row["last_attempt_at"] is None
    assert row["claim_token"] is None
    assert row["claimed_at"] is None
