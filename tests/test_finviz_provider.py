from datetime import UTC, datetime, timedelta

import pytest

from lmio.providers.base import ProviderState
from lmio.providers.finviz_csv import FinvizCSVProvider

HEADER = (
    "Ticker,Company,Sector,Industry,Country,Exchange,Market Cap,Forward P/E,"
    "EPS Growth Quarter Over Quarter,Sales Growth Quarter Over Quarter,Gross Margin,"
    "Operating Margin,Return on Invested Capital,Total Debt/Equity,"
    "Performance (Half Year),200-Day Simple Moving Average,EPS Surprise,"
    "Relative Volume,Average Volume,Volume,Price,Relative Strength Index (14),"
    "Institutional Transactions,Short Float,Short Ratio,Pattern\n"
)
ROW = (
    "TEST,Test Inc,Technology,Software - Application,USA,NASD,2500,20,25%,15%,60%,"
    "20%,18%,0.5,12%,8%,6%,1.4,1500,2000000,40,55,3%,16%,4,Double Bottom\n"
)


def test_finviz_export_maps_authorised_fields() -> None:
    provider = FinvizCSVProvider()
    observed_at = datetime(2026, 7, 31, 1, tzinfo=UTC)

    items = provider.parse(
        HEADER + ROW,
        observed_at=observed_at,
        now=observed_at + timedelta(hours=1),
    )

    assert len(items) == 1
    item = items[0]
    assert item.symbol == "TEST"
    assert item.exchange == "NASDAQ"
    assert item.average_dollar_volume_m == 60
    assert item.revenue_growth_pct == 15
    assert item.eps_growth_pct == 25
    assert item.roic_pct == 18
    assert item.debt_to_equity == 0.5
    assert item.relative_strength_6m == 12
    assert item.price_above_200d_pct == 8
    assert item.institutional_ownership_change_pct == 3
    assert item.short_interest_float_pct == 16
    assert item.days_to_cover == 4
    assert item.chart_pattern == "Double Bottom"
    assert provider.health().state is ProviderState.READY
    assert "1 accepted" in provider.health().detail


def test_finviz_export_excludes_non_equity_and_incomplete_rows() -> None:
    provider = FinvizCSVProvider()
    observed_at = datetime(2026, 7, 31, 1, tzinfo=UTC)
    etf = ROW.replace(
        "TEST,Test Inc,Technology,Software - Application",
        "ETF1,Example ETF,Financial,Exchange Traded Fund",
    )
    missing_market_cap = ROW.replace("TEST,Test Inc", "MISS,Missing Inc").replace(
        ",2500,20,",
        ",,20,",
    )

    items = provider.parse(
        HEADER + ROW + etf + missing_market_cap,
        observed_at=observed_at,
        now=observed_at + timedelta(hours=1),
    )

    assert [item.symbol for item in items] == ["TEST"]
    assert "2 excluded" in provider.health().detail


def test_finviz_export_rejects_missing_columns_duplicate_and_stale_data() -> None:
    observed_at = datetime(2026, 7, 31, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="missing required columns"):
        FinvizCSVProvider().parse(
            "Ticker,Company\nTEST,Test Inc\n",
            observed_at=observed_at,
            now=observed_at,
        )
    with pytest.raises(ValueError, match="duplicate symbol TEST"):
        FinvizCSVProvider().parse(
            HEADER + ROW + ROW,
            observed_at=observed_at,
            now=observed_at,
        )
    with pytest.raises(ValueError, match="stale"):
        FinvizCSVProvider().parse(
            HEADER + ROW,
            observed_at=observed_at,
            now=observed_at + timedelta(hours=49),
        )


def test_finviz_export_requires_timezone_and_eligible_rows() -> None:
    observed_at = datetime(2026, 7, 31, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone"):
        FinvizCSVProvider().parse(
            HEADER + ROW,
            observed_at=datetime(2026, 7, 31, 1),
            now=observed_at,
        )
    etf = ROW.replace(
        "TEST,Test Inc,Technology,Software - Application",
        "ETF1,Example ETF,Financial,Exchange Traded Fund",
    )
    with pytest.raises(ValueError, match="no eligible equity rows"):
        FinvizCSVProvider().parse(
            HEADER + etf,
            observed_at=observed_at,
            now=observed_at,
        )
