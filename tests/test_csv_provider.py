from datetime import UTC, datetime, timedelta

import pytest

from lmio.providers.base import ProviderState
from lmio.providers.csv_snapshot import CSVSnapshotProvider

HEADER = (
    "symbol,company,observed_at,source,price,market_cap_m,"
    "average_dollar_volume_m,revenue_growth_pct\n"
)


def test_csv_accepts_reordered_optional_fields_and_nulls() -> None:
    provider = CSVSnapshotProvider()
    items = provider.parse(
        HEADER + "test,Test Inc,2026-01-01T00:00:00+00:00,licensed export,10,1000,20,\n",
        now=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )

    assert len(items) == 1
    assert items[0].symbol == "TEST"
    assert items[0].revenue_growth_pct is None
    assert items[0].data_completeness == 0
    assert provider.health().state is ProviderState.READY


def test_csv_rejects_missing_required_field() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        CSVSnapshotProvider().parse("symbol,company\nTEST,Test Inc\n")


def test_csv_rejects_invalid_row_with_location() -> None:
    with pytest.raises(ValueError, match="row 2"):
        CSVSnapshotProvider().parse(HEADER + "TEST,Test Inc,not-a-date,source,10,1000,20,5\n")


def test_csv_rejects_empty_export() -> None:
    with pytest.raises(ValueError, match="no data rows"):
        CSVSnapshotProvider().parse(HEADER)


def test_csv_rejects_stale_future_naive_and_duplicate_snapshots() -> None:
    now = datetime(2026, 1, 3, tzinfo=UTC)
    provider = CSVSnapshotProvider()
    with pytest.raises(ValueError, match="stale"):
        provider.parse(
            HEADER + "TEST,Test Inc,2025-12-31T00:00:00+00:00,source,10,1000,20,5\n",
            now=now,
            max_age=timedelta(hours=48),
        )
    with pytest.raises(ValueError, match="future"):
        provider.parse(
            HEADER + "TEST,Test Inc,2026-01-04T00:00:00+00:00,source,10,1000,20,5\n",
            now=now,
        )
    with pytest.raises(ValueError, match="timezone"):
        provider.parse(
            HEADER + "TEST,Test Inc,2026-01-03T00:00:00,source,10,1000,20,5\n",
            now=now,
        )
    duplicate_rows = (
        HEADER
        + "TEST,Test Inc,2026-01-03T00:00:00+00:00,source,10,1000,20,5\n"
        + "test,Test Inc,2026-01-03T00:00:00+00:00,source,10,1000,20,5\n"
    )
    with pytest.raises(ValueError, match="duplicate symbol TEST"):
        provider.parse(duplicate_rows, now=now)


def test_csv_rejects_ambiguous_boolean_values() -> None:
    content = (
        HEADER.rstrip()
        + ",is_common_stock\n"
        + "TEST,Test Inc,2026-01-03T00:00:00+00:00,source,10,1000,20,5,yes\n"
    )

    with pytest.raises(ValueError, match="true or false"):
        CSVSnapshotProvider().parse(
            content,
            now=datetime(2026, 1, 3, tzinfo=UTC),
        )


def test_csv_health_is_not_ready_before_successful_parse() -> None:
    assert CSVSnapshotProvider().health().state is ProviderState.CONFIGURED_NOT_VERIFIED
