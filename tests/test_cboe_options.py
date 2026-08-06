from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from lmio.config import Settings
from lmio.providers.cboe_options import (
    CBOE_MOST_ACTIVE_ENDPOINT,
    CboeMostActiveProvider,
    parse_cboe_most_active,
)
from lmio.service import LMIOService


def cboe_payload(*, empty: bool = False) -> dict[str, object]:
    calls = (
        []
        if empty
        else [
            {"symbol": "NVDA", "expires": "2026-08-21", "strike": 200, "volume": 120000},
            {"symbol": "SPY", "expires": "2026-08-21", "strike": 700, "volume": 90000},
        ]
    )
    puts = (
        []
        if empty
        else [{"symbol": "NVDA", "expires": "2026-08-21", "strike": 180, "volume": 80000}]
    )
    return {
        "categories": [
            {"category": "all", "calls": [], "puts": []},
            {"category": "equity", "calls": calls, "puts": puts},
        ],
        "dt": "2026-08-06T15:30:00-04:00",
    }


def test_cboe_parser_aggregates_only_bounded_equity_leaderboard_rows() -> None:
    snapshot = parse_cboe_most_active(
        cboe_payload(),
        retrieved_at=datetime(2026, 8, 6, 20, tzinfo=UTC),
    )

    assert snapshot.total_contracts == 3
    assert snapshot.market_timestamp == datetime(2026, 8, 6, 19, 30, tzinfo=UTC)
    assert snapshot.high_volume_tickers() == [
        {
            "symbol": "NVDA",
            "leaderboard_volume": 200000,
            "call_volume": 120000,
            "put_volume": 80000,
            "contract_count": 2,
        },
        {
            "symbol": "SPY",
            "leaderboard_volume": 90000,
            "call_volume": 90000,
            "put_volume": 0,
            "contract_count": 1,
        },
    ]


def test_cboe_provider_rejects_non_json_responses() -> None:
    provider = CboeMostActiveProvider(
        transport=lambda *_args: httpx.Response(
            200,
            text="not json",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", CBOE_MOST_ACTIVE_ENDPOINT),
        )
    )

    with pytest.raises(ValueError, match="unexpected content type"):
        provider.snapshot()


def test_closed_market_check_does_not_replace_last_non_empty_snapshot(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    payloads = iter([cboe_payload(), cboe_payload(empty=True)])

    def transport(*_args: object) -> httpx.Response:
        return httpx.Response(
            200,
            json=next(payloads),
            headers={"content-type": "application/json"},
            request=httpx.Request("GET", CBOE_MOST_ACTIVE_ENDPOINT),
        )

    provider = CboeMostActiveProvider(transport=transport)
    first = service.refresh_cboe_options(provider=provider)
    second = service.refresh_cboe_options(provider=provider)
    events = [
        item
        for item in service.store.history_json("provider_health", 10)
        if item["provider"] == "cboe_options_most_active"
    ]

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert events[0]["state"] == "no_current_session_data"
    assert events[0]["payload"]["total_contracts"] == 0
    assert events[1]["state"] == "ready"
    assert events[1]["payload"]["total_contracts"] == 3
