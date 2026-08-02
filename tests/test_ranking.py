from datetime import UTC, datetime, timedelta
from random import Random

from lmio.demo import demo_universe
from lmio.domain import DataProvenance, Strategy
from lmio.ranking import rank_top10
from lmio.screens import run_core_screens


def _candidates(now: datetime):
    snapshots = [
        item.model_copy(
            update={
                "provenance": DataProvenance.HISTORICAL_AUTHORISED,
                "observed_at": now,
            }
        )
        for item in demo_universe()
    ]
    candidates = run_core_screens(snapshots)
    return [
        candidate.model_copy(
            update={
                "evidence": [
                    item.model_copy(update={"observed_at": now}) for item in candidate.evidence
                ]
            }
        )
        for candidate in candidates
    ]


def test_top10_ranking_is_stable_deduplicated_and_order_independent() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    candidates = _candidates(now)
    duplicate = candidates[0].model_copy(
        update={"strategy": Strategy.NEWS_DRIVEN, "total_score": candidates[0].total_score - 1}
    )
    inputs = [*candidates, duplicate]
    shuffled = list(inputs)
    Random(42).shuffle(shuffled)

    first = rank_top10(inputs, run_id="run-1", now=now)
    second = rank_top10(shuffled, run_id="run-1", now=now)

    assert [(item.candidate.symbol, item.adjusted_score) for item in first] == [
        (item.candidate.symbol, item.adjusted_score) for item in second
    ]
    assert len({item.candidate.symbol for item in first}) == len(first)
    assert any(item.alternative_strategies for item in first)


def test_ranking_penalises_stale_and_incomplete_evidence_and_rejects_demo_rows() -> None:
    now = datetime(2026, 8, 1, 12, tzinfo=UTC)
    fresh = _candidates(now)[0]
    degraded = fresh.model_copy(
        update={
            "symbol": "STALE",
            "source_completeness": 0.5,
            "missing_fields": ["field_a", "field_b"],
            "evidence": [
                item.model_copy(update={"observed_at": now - timedelta(days=2)})
                for item in fresh.evidence
            ],
        }
    )
    demo = fresh.model_copy(
        update={"symbol": "DEMO", "provenance": DataProvenance.SYNTHETIC_REPLAY}
    )

    ranked = rank_top10([degraded, fresh, demo], run_id="run-2", now=now)

    assert [item.candidate.symbol for item in ranked] == [fresh.symbol, "STALE"]
    assert ranked[0].adjusted_score > ranked[1].adjusted_score
    assert "stale_penalty=15.0000" in ranked[1].ranking_reasons
