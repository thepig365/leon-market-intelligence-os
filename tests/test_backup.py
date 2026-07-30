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
    assert manifest["schema_versions"] == [4]
    assert manifest["counts"] == store.counts()
    assert manifest["sha256"]
    assert manifest["bytes"] > 0


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


def test_schema_four_upgrades_an_existing_schema_three_store(tmp_path: Path) -> None:
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

    assert store.schema_versions() == [3, 4]
    with store.connection() as upgraded:
        row = upgraded.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'ingestion_dedup'"
        ).fetchone()
    assert row is not None
