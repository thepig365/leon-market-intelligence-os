from datetime import UTC, datetime, timedelta

from lmio.freshness import (
    DataType,
    FreshnessState,
    blocks_new_recommendation,
    evaluate_freshness,
)


def test_freshness_uses_data_type_specific_thresholds() -> None:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    market = evaluate_freshness(
        DataType.MARKET_SNAPSHOT,
        as_of=now - timedelta(hours=2),
        retrieved_at=now - timedelta(hours=2),
        source="finviz",
        snapshot_id="finviz:one",
        now=now,
    )
    ownership = evaluate_freshness(
        DataType.INSTITUTIONAL_OWNERSHIP,
        as_of=now - timedelta(days=40),
        retrieved_at=now - timedelta(days=40),
        source="sec",
        snapshot_id="sec:one",
        now=now,
    )

    assert market.freshness_state is FreshnessState.STALE
    assert blocks_new_recommendation(DataType.MARKET_SNAPSHOT, market)
    assert ownership.freshness_state is FreshnessState.FRESH


def test_missing_as_of_is_unknown_and_fail_closed_for_price() -> None:
    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    freshness = evaluate_freshness(
        DataType.PRICE_CONFIRMATION,
        as_of=None,
        retrieved_at=now,
        source="missing",
        snapshot_id="missing:one",
        now=now,
    )
    assert freshness.model_dump(mode="json") == {
        "as_of": None,
        "retrieved_at": "2026-08-02T12:00:00Z",
        "age_seconds": None,
        "freshness_state": "unknown",
        "source": "missing",
        "snapshot_id": "missing:one",
    }
    assert blocks_new_recommendation(DataType.PRICE_CONFIRMATION, freshness)
