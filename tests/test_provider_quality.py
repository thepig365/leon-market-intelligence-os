from datetime import UTC, datetime, timedelta

from lmio.demo import demo_universe
from lmio.provider_quality import (
    BatchState,
    assess_snapshot_batch,
    classify_provider_failure,
)


def test_provider_batch_accepts_valid_and_degraded_data() -> None:
    now = datetime(2026, 7, 30, tzinfo=UTC)
    valid = assess_snapshot_batch(demo_universe(), now=now)
    degraded_items = [demo_universe()[0].model_copy(update={"data_completeness": 0.5})]
    degraded = assess_snapshot_batch(degraded_items, now=now)

    assert valid.state is BatchState.VALID
    assert valid.accepted is True
    assert degraded.state is BatchState.DEGRADED
    assert degraded.accepted is True


def test_provider_batch_rejects_empty_duplicate_stale_and_order_errors() -> None:
    now = datetime(2026, 7, 30, tzinfo=UTC)
    item = demo_universe()[0]
    duplicate = assess_snapshot_batch([item, item], now=now)
    stale = assess_snapshot_batch(
        [item.model_copy(update={"observed_at": now - timedelta(days=2)})],
        now=now,
    )
    later = item.model_copy(update={"symbol": "LATER", "observed_at": now})
    earlier = item.model_copy(
        update={"symbol": "EARLIER", "observed_at": now - timedelta(minutes=1)}
    )
    out_of_order = assess_snapshot_batch([later, earlier], now=now)

    assert assess_snapshot_batch([], now=now).state is BatchState.EMPTY
    assert duplicate.state is BatchState.DUPLICATE
    assert stale.state is BatchState.STALE
    assert out_of_order.state is BatchState.OUT_OF_ORDER
    assert all(not result.accepted for result in (duplicate, stale, out_of_order))


def test_provider_failures_classify_rate_limits_and_outages() -> None:
    assert classify_provider_failure(RuntimeError("HTTP 429 rate limit")) is BatchState.RATE_LIMITED
    assert classify_provider_failure(ConnectionError("offline")) is BatchState.UNAVAILABLE
