import json
from pathlib import Path

from lmio.providers.sec import SECProvider
from lmio.sec_monitor import monitor_sec
from lmio.store import RuntimeStore


def test_monitor_persists_official_filings_once(tmp_path: Path) -> None:
    response = {
        "cik": "320193",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-26-000001"],
                "filingDate": ["2026-01-02"],
                "form": ["8-K"],
                "primaryDocument": ["report.htm"],
            }
        },
    }

    def transport(_url: str, _headers: dict[str, str]) -> bytes:
        return json.dumps(response).encode()

    provider = SECProvider("LMIO admin@example.test", transport)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()

    first = monitor_sec(provider, store, {"AAPL": "320193"})
    second = monitor_sec(provider, store, {"AAPL": "320193"})

    assert first == {"symbols": 1, "checked": 1, "inserted": 1}
    assert second == {"symbols": 1, "checked": 1, "inserted": 0}
    assert store.counts()["news_events"] == 1
