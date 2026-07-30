from pathlib import Path

from lmio.store import RuntimeStore
from lmio.telegram import queue_or_send


def test_telegram_is_queued_without_credentials_and_deduplicated(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    assert queue_or_send(store, "中文测试简报") == "queued_not_configured"
    assert queue_or_send(store, "中文测试简报") == "queued_not_configured"
    assert store.counts()["telegram_deliveries"] == 1
