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
    assert {item["model"] for item in result.model_components} == {
        "Blended FCFF/Owner Earnings DCF",
        "EV/Revenue",
        "EV/EBITDA",
        "P/E",
        "P/FCF",
    }
    assert result.assumptions["ev_revenue_multiple"] == 7
    assert result.assumptions["pe_multiple"] == 24
    assert len(result.sensitivity) == 3


def test_wacc_must_exceed_terminal_growth() -> None:
    invalid = meta_acceptance_input().model_copy(
        update={"discount_rate": 0.03, "terminal_growth": 0.03}
    )

    with pytest.raises(ValueError, match="discount_rate must exceed"):
        run_valuation(invalid)


def test_missing_multiple_inputs_reduce_multi_model_confidence() -> None:
    cash_flow_only = meta_acceptance_input().model_copy(
        update={
            "revenue": None,
            "ebitda": None,
            "net_income": None,
            "ev_revenue_multiple": None,
            "ev_ebitda_multiple": None,
            "pe_multiple": None,
            "p_fcf_multiple": None,
        }
    )

    result = run_valuation(cash_flow_only)

    assert len(result.model_components) == 1
    assert result.multi_model_fair_value.warning is not None
    assert result.confidence < cash_flow_only.confidence


def test_non_positive_multiple_value_fails_to_low_confidence_not_division_error() -> None:
    distressed = meta_acceptance_input().model_copy(
        update={
            "net_cash": -2_000_000,
            "revenue": 100,
            "ev_revenue_multiple": 1,
            "ebitda": None,
            "net_income": None,
            "ev_ebitda_multiple": None,
            "pe_multiple": None,
            "p_fcf_multiple": None,
        }
    )

    result = run_valuation(distressed)

    assert "non-positive equity value" in str(result.multi_model_fair_value.warning)
    assert result.confidence < distressed.confidence


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
