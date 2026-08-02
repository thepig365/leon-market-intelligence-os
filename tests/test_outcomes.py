import pytest

from lmio.outcomes import (
    OutcomeStatus,
    TimedPrice,
    calculate_horizon_outcomes,
    calculate_outcome,
    evaluate_timed_horizon,
    one_hour_due_at,
    summarise_performance,
)


def test_outcome_tracks_final_and_excursions() -> None:
    result = calculate_outcome(100, [95, 110, 105])

    assert result.return_pct == 0.05
    assert result.max_adverse_excursion_pct == -0.05
    assert result.max_favourable_excursion_pct == 0.1


def test_outcome_rejects_invalid_prices() -> None:
    with pytest.raises(ValueError, match="positive"):
        calculate_outcome(0, [1])


def test_horizon_outcomes_and_benchmarks() -> None:
    outcomes = calculate_horizon_outcomes(100, [101, 102, 103, 104, 105, 106, 107])

    assert set(outcomes) == {"1h", "close", "1d", "5d"}
    summary = summarise_performance(
        [outcomes["1d"], outcomes["5d"]],
        spy_returns=[0.01, 0.02],
        sector_returns=[0.02, 0.03],
    )
    assert summary.sample_size == 2
    assert summary.hit_rate == 1
    assert summary.average_excess_vs_spy is not None
    assert summary.average_mfe > 0


def test_one_hour_outcome_never_uses_same_timestamp_price() -> None:
    from datetime import UTC, datetime, timedelta

    signal_time = datetime(2026, 8, 3, 14, 30, tzinfo=UTC)
    result = evaluate_timed_horizon(
        horizon="1h",
        signal_time=signal_time,
        signal_price=100,
        benchmark_price=500,
        due_at=one_hour_due_at(signal_time),
        prices=[TimedPrice(signal_time, 100, 500)],
        now=signal_time + timedelta(hours=2),
    )
    assert result.status is OutcomeStatus.UNAVAILABLE
    assert result.return_pct is None


def test_timed_outcome_tracks_benchmark_excursions_and_invalidation() -> None:
    from datetime import UTC, datetime, timedelta

    signal_time = datetime(2026, 8, 3, 14, 30, tzinfo=UTC)
    due = one_hour_due_at(signal_time)
    result = evaluate_timed_horizon(
        horizon="1h",
        signal_time=signal_time,
        signal_price=100,
        benchmark_price=500,
        due_at=due,
        prices=[
            TimedPrice(signal_time + timedelta(minutes=20), 95, 501),
            TimedPrice(due, 105, 505),
        ],
        now=due,
        invalidation_price=96,
    )
    assert result.status is OutcomeStatus.COMPLETED
    assert result.return_pct == 0.05
    assert result.benchmark_return_pct == 0.01
    assert result.abnormal_return_pct == 0.04
    assert result.invalidation_triggered is True
