from datetime import UTC, datetime
from pathlib import Path

import httpx

from lmio.config import Settings
from lmio.providers.finviz_api import (
    FINVIZ_EXPORT_URL,
    VIX_HISTORY_URL,
    FinvizAPIProvider,
)
from lmio.service import LMIOService

HEADER = "Ticker,Company,Sector,Industry,Country,Exchange,Market Cap,Average Volume,Price,Change\n"


def _market_csv() -> bytes:
    rows = [
        "SPY,SPDR S&P 500 ETF,Financial,Exchange Traded Fund,USA,AMEX,500000,80000,650,0.80%",
        "QQQ,Invesco QQQ ETF,Technology,Exchange Traded Fund,USA,NASD,350000,60000,600,1.00%",
        "IWM,iShares Russell 2000 ETF,Financial,Exchange Traded Fund,USA,AMEX,70000,40000,"
        "500,0.60%",
    ]
    rows.extend(
        f"STK{index:03d},Company {index},Technology,Software,USA,NASD,2500,1500,40,"
        f"{'0.50%' if index < 60 else '-0.25%'}"
        for index in range(100)
    )
    return (HEADER + "\n".join(rows) + "\n").encode()


def _response(url: str, content: bytes) -> httpx.Response:
    return httpx.Response(
        200,
        content=content,
        headers={"content-type": "text/csv"},
        request=httpx.Request("GET", url),
    )


def _provider() -> FinvizAPIProvider:
    return FinvizAPIProvider(
        "private-token",
        transport=lambda *_args: _response(FINVIZ_EXPORT_URL, _market_csv()),
        vix_transport=lambda *_args: _response(
            VIX_HISTORY_URL,
            b"DATE,OPEN,HIGH,LOW,CLOSE\n07/30/2026,18,19,17,17.09\n07/31/2026,16,18,15,15.99\n",
        ),
    )


def test_market_environment_uses_benchmarks_breadth_and_official_vix() -> None:
    provider = _provider()
    snapshots = provider.snapshots()

    environment = provider.market_environment(
        snapshots,
        now=datetime(2026, 8, 2, 1, tzinfo=UTC),
    )

    assert len(snapshots) == 100
    assert environment.spy_return_pct == 0.8
    assert environment.qqq_return_pct == 1
    assert environment.iwm_return_pct == 0.6
    assert environment.vix == 15.99
    assert environment.breadth_pct == 60
    assert environment.breadth_observations == 100
    assert environment.vix_observed_on == "2026-07-31"


def test_finviz_refresh_persists_verified_market_regime(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    result = service.refresh_finviz(provider=_provider())
    report = service.store.latest_json("reports")
    regimes = service.store.history_json("market_regimes")

    assert result["status"] == "completed"
    assert report is not None
    assert report["regime"]["label"] == "Risk-On"
    assert report["regime"]["confidence"] == 0.8
    assert regimes[0]["payload"]["environment"]["breadth_observations"] == 100
    health = service.store.history_json("provider_health")
    assert any(
        item["provider"] == "market_environment" and item["state"] == "ready" for item in health
    )
