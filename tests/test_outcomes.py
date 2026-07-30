import pytest

from lmio.outcomes import calculate_outcome


def test_outcome_tracks_final_and_excursions() -> None:
    result = calculate_outcome(100, [95, 110, 105])

    assert result.return_pct == 0.05
    assert result.max_adverse_excursion_pct == -0.05
    assert result.max_favourable_excursion_pct == 0.1


def test_outcome_rejects_invalid_prices() -> None:
    with pytest.raises(ValueError, match="positive"):
        calculate_outcome(0, [1])
