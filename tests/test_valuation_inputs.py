from datetime import UTC, datetime

from lmio.domain import DataProvenance
from lmio.valuation_inputs import FinancialEvidence, prepare_valuation_input


def evidence(**updates):
    values = {
        "symbol": "TEST",
        "provenance": DataProvenance.HISTORICAL_AUTHORISED,
        "observed_at": datetime(2026, 8, 1, tzinfo=UTC),
        "source_fields": {
            "operating_cash_flow": 100,
            "capex": 30,
            "net_cash": 20,
            "diluted_shares": 10,
            "market_price": 40,
        },
        "source_references": {
            "operating_cash_flow": "https://example.test/filing",
            "market_price": "https://example.test/market",
        },
        "assumptions": {
            "growth_rate": 0.08,
            "terminal_growth": 0.03,
            "discount_rate": 0.1,
            "forecast_years": 5,
        },
    }
    values.update(updates)
    return FinancialEvidence.model_validate(values)


def test_builder_preserves_sources_assumptions_and_derivations() -> None:
    prepared = prepare_valuation_input(evidence())

    assert prepared.status == "ready"
    assert prepared.derived_calculations == {"strict_fcf": 70}
    assert prepared.source_references["market_price"].endswith("/market")
    assert prepared.valuation_input is not None
    assert prepared.valuation_input.provenance == "historical_authorised"


def test_builder_never_invents_missing_inputs() -> None:
    item = evidence()
    item.source_fields["net_cash"] = None

    prepared = prepare_valuation_input(item)

    assert prepared.status == "blocked"
    assert prepared.missing_fields == ["net_cash"]
    assert prepared.valuation_input is None


def test_builder_routes_unsupported_companies_safely() -> None:
    prepared = prepare_valuation_input(evidence(company_type="bank"))

    assert prepared.status == "unsupported"
    assert prepared.route == "bank_equity_and_book_value_model_required"
    assert prepared.valuation_input is None
