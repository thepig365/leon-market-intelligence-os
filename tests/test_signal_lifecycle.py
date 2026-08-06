from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lmio.config import Settings
from lmio.demo import demo_universe
from lmio.domain import DataProvenance, SignalRecord
from lmio.ranking import rank_top10
from lmio.screens import run_core_screens
from lmio.service import LMIOService


def _candidate(now: datetime):
    snapshot = demo_universe()[0].model_copy(
        update={
            "provenance": DataProvenance.HISTORICAL_AUTHORISED,
            "observed_at": now,
        }
    )
    candidate = run_core_screens([snapshot])[0]
    return candidate.model_copy(
        update={
            "evidence": [
                item.model_copy(update={"observed_at": now}) for item in candidate.evidence
            ]
        }
    )


def _snapshot(service: LMIOService, symbol: str, price: float, observed_at: datetime) -> None:
    service.store.put_provider_snapshot(
        f"{symbol}:{observed_at.isoformat()}",
        provider="authorised-test-provider",
        symbol=symbol,
        company=symbol,
        observed_at=observed_at.isoformat(),
        payload={
            "symbol": symbol,
            "price": price,
            "observed_at": observed_at.isoformat(),
            "provenance": "historical_authorised",
        },
    )


def test_signal_requires_same_operator_approval_and_current_evidence(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    candidate = _candidate(now)
    ranked = rank_top10([candidate], run_id="run-approved", now=now)[0]
    service.store.append_json(
        "top10_rankings",
        {
            "run_id": "run-approved",
            "symbol": candidate.symbol,
            "rank": 1,
            "payload": ranked.model_dump(mode="json"),
        },
    )
    service.store.append_json(
        "top3_evaluations",
        {
            "symbol": candidate.symbol,
            "state": "top3_selected",
            "payload": {"run_id": "run-approved", "state": "top3_selected"},
        },
    )
    plan_id = service.store.append_json(
        "conditional_plans",
        {
            "symbol": candidate.symbol,
            "state": "plan_ready",
            "version": "conditional-plan-v1",
            "payload": {
                "run_id": "run-approved",
                "expires_at": (now + timedelta(days=1)).isoformat(),
                "invalidation_condition": candidate.invalidation,
                "created_by": "lmio-system",
            },
        },
    )
    _snapshot(service, candidate.symbol, candidate.market_price, now)
    _snapshot(service, "SPY", 500, now)

    with pytest.raises(ValueError, match="authenticated operator"):
        service.create_signal_from_approved_plan(plan_id, actor="leon")

    service.store.append_json(
        "trade_plan_transitions",
        {
            "symbol": candidate.symbol,
            "previous_state": "waiting_confirmation",
            "new_state": "plan_ready",
            "payload": {
                "run_id": "run-approved",
                "actor": "leon",
                "reason": "Leon approved the research plan.",
            },
        },
    )
    result = service.create_signal_from_approved_plan(plan_id, actor="leon")

    assert result["status"] == "created"
    assert result["execution_capability"] is False
    signal = service.store.history_json("signals", 1)[0]["payload"]
    assert signal["approved_by"] == "leon"
    assert signal["run_id"] == "run-approved"


def test_outcome_progresses_each_horizon_once_with_benchmark_lineage(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    signal_time = datetime(2026, 6, 1, 14, 30, tzinfo=UTC)
    candidate = _candidate(signal_time)
    signal = SignalRecord(
        signal_id="signal-lifecycle",
        run_id="run-lifecycle",
        candidate_id="candidate-lifecycle",
        symbol=candidate.symbol,
        strategy=candidate.strategy,
        created_at=signal_time,
        signal_price=100,
        benchmark="SPY",
        benchmark_price=500,
        source_snapshot_ids=["provider-snapshot-origin"],
        scores=candidate.scores,
        candidate_state=candidate.state,
        plan_id="plan-lifecycle",
        approved_by="leon",
        invalidation_conditions=[candidate.invalidation],
        provenance=DataProvenance.HISTORICAL_AUTHORISED,
        model_versions={"signal": "signal-evidence-v1"},
    )
    service.store.append_json(
        "signals",
        {
            "symbol": signal.symbol,
            "strategy": signal.strategy,
            "state": "active_research_signal",
            "payload": signal.model_dump(mode="json"),
        },
    )
    due_times = service._outcome_due_times(signal_time)
    for index, observed_at in enumerate(due_times.values(), start=1):
        _snapshot(service, signal.symbol, 100 + index, observed_at)
        _snapshot(service, "SPY", 500 + index, observed_at)

    first = service.process_due_outcomes(now=max(due_times.values()) + timedelta(hours=1))
    second = service.process_due_outcomes(now=max(due_times.values()) + timedelta(hours=2))

    assert first["completed"] == 5
    assert second["completed"] == 0
    assert second["unchanged"] == 5
    outcomes = service.store.history_json("signal_outcomes", 20)
    assert {item["horizon"] for item in outcomes} == {"1h", "close", "1d", "5d", "20d"}
    assert all(item["payload"]["actual_observation_time"] for item in outcomes)
    assert all(len(item["payload"]["evidence_references"]) >= 1 for item in outcomes)
    assert any(
        "|provider-snapshot-" in ref
        for item in outcomes
        for ref in item["payload"]["evidence_references"]
    )
