from pathlib import Path

import httpx
import pytest

from lmio.config import Settings
from lmio.domain import DataProvenance
from lmio.providers.base import ProviderState
from lmio.providers.finviz_api import FINVIZ_EXPORT_URL, FinvizAPIProvider
from lmio.service import LMIOService

HEADER = (
    "Ticker,Company,Sector,Industry,Country,Exchange,Market Cap,Forward P/E,"
    "EPS Growth Quarter Over Quarter,Sales Growth Quarter Over Quarter,Gross Margin,"
    "Operating Margin,Return on Invested Capital,Total Debt/Equity,"
    "Performance (Half Year),200-Day Simple Moving Average,EPS Surprise,"
    "Relative Volume,Average Volume,Volume,Price,Relative Strength Index (14),"
    "Institutional Transactions,Short Float,Short Ratio\n"
)
ROW = (
    "TEST,Test Inc,Technology,Software - Application,USA,NASD,2500,20,25%,15%,60%,"
    "20%,18%,0.5,12%,8%,6%,1.4,1500,2000000,40,55,3%,16%,4\n"
)


def response(status: int, content: bytes = b"") -> httpx.Response:
    return httpx.Response(
        status,
        content=content,
        headers={"content-type": "text/csv"},
        request=httpx.Request("GET", FINVIZ_EXPORT_URL),
    )


def test_finviz_api_fetches_authorised_csv_without_exposing_token() -> None:
    calls: list[tuple[str, dict[str, str], float]] = []

    def transport(url: str, params: dict[str, str], timeout: float) -> httpx.Response:
        calls.append((url, params, timeout))
        return response(200, (HEADER + ROW).encode())

    provider = FinvizAPIProvider("private-token", transport=transport)
    items = provider.snapshots()

    assert [item.symbol for item in items] == ["TEST"]
    assert items[0].provenance is DataProvenance.LIVE_AUTHORISED
    assert calls[0][0] == FINVIZ_EXPORT_URL
    assert calls[0][1]["auth"] == "private-token"
    assert provider.health().state is ProviderState.READY
    assert "private-token" not in provider.health().detail


def test_finviz_api_limits_an_authorised_lookup_to_requested_symbols() -> None:
    calls: list[dict[str, str]] = []

    def transport(_url: str, params: dict[str, str], _timeout: float) -> httpx.Response:
        calls.append(params)
        return response(200, (HEADER + ROW).encode())

    provider = FinvizAPIProvider("private-token", transport=transport)

    assert [item.symbol for item in provider.snapshots(symbols=["test"])] == ["TEST"]
    assert calls[0]["t"] == "TEST"
    assert "1 of 1 requested symbols" in provider.health().detail


def test_finviz_api_backs_off_on_rate_limit() -> None:
    responses = [response(429), response(429), response(200, (HEADER + ROW).encode())]
    waits: list[float] = []

    def transport(_url: str, _params: dict[str, str], _timeout: float) -> httpx.Response:
        return responses.pop(0)

    provider = FinvizAPIProvider(
        "private-token",
        transport=transport,
        wait=waits.append,
    )

    assert len(provider.snapshots()) == 1
    assert waits == [5.0, 10.0]


def test_finviz_api_rejects_missing_token_and_unexpected_content() -> None:
    with pytest.raises(RuntimeError, match="not configured"):
        FinvizAPIProvider("").snapshots()

    provider = FinvizAPIProvider(
        "private-token",
        transport=lambda *_args: httpx.Response(
            200,
            content=b"<html>not csv</html>",
            headers={"content-type": "text/html"},
            request=httpx.Request("GET", FINVIZ_EXPORT_URL),
        ),
    )
    with pytest.raises(ValueError, match="unexpected content"):
        provider.snapshots()


def test_refresh_runs_screen_and_queues_telegram_when_not_configured(tmp_path: Path) -> None:
    provider = FinvizAPIProvider(
        "private-token",
        transport=lambda *_args: response(200, (HEADER + ROW).encode()),
    )
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    result = service.refresh_finviz(provider=provider)

    assert result["status"] == "completed"
    assert result["equities_received"] == 1
    assert result["telegram"] == "queued_not_configured"
    assert service.store.latest_provider_health()["state"] == "ready"


def test_refresh_preserves_existing_data_when_provider_fails(tmp_path: Path) -> None:
    provider = FinvizAPIProvider(
        "private-token",
        transport=lambda *_args: response(503),
    )
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    with pytest.raises(RuntimeError, match="failed safely"):
        service.refresh_finviz(provider=provider)

    assert service.store.latest_provider_health()["state"] == "unavailable"
    assert service.store.counts()["reports"] == 0
