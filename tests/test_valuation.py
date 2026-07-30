import pytest

from lmio.demo import meta_acceptance_input
from lmio.valuation import run_valuation, safety_label


def test_meta_case_shows_three_distinct_values() -> None:
    result = run_valuation(meta_acceptance_input())

    assert result.strict_fcf.base < result.normalised_owner_earnings.base
    assert result.strict_fcf.base != result.multi_model_fair_value.base
    assert result.normalised_owner_earnings.base != result.multi_model_fair_value.base
    assert result.assumptions["reported_fcf"] == 30_000
    assert result.assumptions["owner_earnings"] == 72_000
    assert len(result.sensitivity) == 3


def test_wacc_must_exceed_terminal_growth() -> None:
    invalid = meta_acceptance_input().model_copy(
        update={"discount_rate": 0.03, "terminal_growth": 0.03}
    )

    with pytest.raises(ValueError, match="discount_rate must exceed"):
        run_valuation(invalid)


@pytest.mark.parametrize(
    ("margin", "label"),
    [
        (0.31, "Substantial"),
        (0.25, "Attractive"),
        (0.15, "Moderately undervalued"),
        (0, "Near fair value"),
        (-0.2, "Moderately overvalued"),
        (-0.4, "Substantially overvalued"),
    ],
)
def test_safety_labels(margin: float, label: str) -> None:
    assert safety_label(margin) == label
