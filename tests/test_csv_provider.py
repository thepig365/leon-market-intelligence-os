import pytest

from lmio.providers.csv_snapshot import CSVSnapshotProvider

HEADER = (
    "symbol,company,observed_at,source,price,market_cap_m,"
    "average_dollar_volume_m,revenue_growth_pct\n"
)


def test_csv_accepts_reordered_optional_fields_and_nulls() -> None:
    items = CSVSnapshotProvider().parse(
        HEADER + "TEST,Test Inc,2026-01-01T00:00:00+00:00,licensed export,10,1000,20,\n"
    )

    assert len(items) == 1
    assert items[0].symbol == "TEST"
    assert items[0].revenue_growth_pct is None


def test_csv_rejects_missing_required_field() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        CSVSnapshotProvider().parse("symbol,company\nTEST,Test Inc\n")


def test_csv_rejects_invalid_row_with_location() -> None:
    with pytest.raises(ValueError, match="row 2"):
        CSVSnapshotProvider().parse(HEADER + "TEST,Test Inc,not-a-date,source,10,1000,20,5\n")


def test_csv_rejects_empty_export() -> None:
    with pytest.raises(ValueError, match="no data rows"):
        CSVSnapshotProvider().parse(HEADER)
