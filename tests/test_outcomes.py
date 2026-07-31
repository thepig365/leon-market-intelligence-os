import pytest

from lmio.outcomes import (
    calculate_horizon_outcomes,
    calculate_outcome,
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
