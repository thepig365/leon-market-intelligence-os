"""Three-perspective valuation engine with reproducible assumptions."""

from datetime import UTC, datetime

from lmio.domain import ValuationInput, ValuationPerspective, ValuationResult

CALCULATION_VERSION = "valuation-v2"


def _dcf_per_share(
    cash_flow: float,
    growth_rate: float,
    terminal_growth: float,
    discount_rate: float,
    years: int,
    net_cash: float,
    shares: float,
) -> tuple[float, float]:
    if discount_rate <= terminal_growth:
        raise ValueError("discount_rate must exceed terminal_growth")
    present_value = 0.0
    projected = cash_flow
    for year in range(1, years + 1):
        projected *= 1 + growth_rate
        present_value += projected / ((1 + discount_rate) ** year)
    terminal_value = projected * (1 + terminal_growth) / (discount_rate - terminal_growth)
    discounted_terminal = terminal_value / ((1 + discount_rate) ** years)
    enterprise = present_value + discounted_terminal
    terminal_share = discounted_terminal / enterprise if enterprise else 0
    return (enterprise + net_cash) / shares, terminal_share


def _perspective(
    name: str,
    cash_flow: float,
    data: ValuationInput,
    applicability: str,
    warning: str | None = None,
) -> tuple[ValuationPerspective, float]:
    base, terminal_share = _dcf_per_share(
        cash_flow,
        data.growth_rate,
        data.terminal_growth,
        data.discount_rate,
        data.forecast_years,
        data.net_cash,
        data.diluted_shares,
    )
    pessimistic, _ = _dcf_per_share(
        cash_flow * 0.9,
        max(-0.05, data.growth_rate - 0.04),
        max(0, data.terminal_growth - 0.005),
        data.discount_rate + 0.015,
        data.forecast_years,
        data.net_cash,
        data.diluted_shares,
    )
    optimistic, _ = _dcf_per_share(
        cash_flow * 1.05,
        data.growth_rate + 0.03,
        min(data.discount_rate - 0.01, data.terminal_growth + 0.01),
        data.discount_rate - 0.01,
        data.forecast_years,
        data.net_cash,
        data.diluted_shares,
    )
    return (
        ValuationPerspective(
            name=name,
            pessimistic=round(pessimistic, 2),
            base=round(base, 2),
            optimistic=round(optimistic, 2),
            applicability=applicability,
            warning=warning,
        ),
        terminal_share,
    )


def _multiple_value(
    operating_metric: float,
    multiple: float,
    net_cash: float,
    diluted_shares: float,
) -> float:
    return ((operating_metric * multiple) + net_cash) / diluted_shares


def _multi_model_perspective(
    data: ValuationInput,
    *,
    reported_fcf: float,
    blended_dcf_value: float,
) -> tuple[ValuationPerspective, list[dict[str, float | str]], float]:
    components: list[dict[str, float | str]] = [
        {
            "model": "Blended FCFF/Owner Earnings DCF",
            "value_per_share": round(blended_dcf_value, 2),
            "weight": 1.0,
        }
    ]
    if data.revenue is not None and data.ev_revenue_multiple is not None:
        components.append(
            {
                "model": "EV/Revenue",
                "value_per_share": round(
                    _multiple_value(
                        data.revenue,
                        data.ev_revenue_multiple,
                        data.net_cash,
                        data.diluted_shares,
                    ),
                    2,
                ),
                "weight": 1.0,
            }
        )
    if data.ebitda is not None and data.ev_ebitda_multiple is not None:
        components.append(
            {
                "model": "EV/EBITDA",
                "value_per_share": round(
                    _multiple_value(
                        data.ebitda,
                        data.ev_ebitda_multiple,
                        data.net_cash,
                        data.diluted_shares,
                    ),
                    2,
                ),
                "weight": 1.0,
            }
        )
    if data.net_income is not None and data.net_income > 0 and data.pe_multiple is not None:
        components.append(
            {
                "model": "P/E",
                "value_per_share": round(
                    data.net_income * data.pe_multiple / data.diluted_shares,
                    2,
                ),
                "weight": 1.0,
            }
        )
    if reported_fcf > 0 and data.p_fcf_multiple is not None:
        components.append(
            {
                "model": "P/FCF",
                "value_per_share": round(
                    reported_fcf * data.p_fcf_multiple / data.diluted_shares,
                    2,
                ),
                "weight": 1.0,
            }
        )
    total_weight = sum(float(item["weight"]) for item in components)
    base = (
        sum(float(item["value_per_share"]) * float(item["weight"]) for item in components)
        / total_weight
    )
    values = [float(item["value_per_share"]) for item in components]
    lowest = min(values)
    highest = max(values)
    pessimistic = lowest * (1.1 if lowest < 0 else 0.9)
    optimistic = highest * (1.1 if highest >= 0 else 0.9)
    warning = None
    confidence_multiplier = 1.0
    if len(components) == 1:
        warning = "Only one applicable model has approved inputs; confidence reduced."
        confidence_multiplier = 0.65
    elif lowest <= 0:
        warning = "At least one applicable model implies non-positive equity value."
        confidence_multiplier = 0.6
    elif highest / lowest > 1.75:
        warning = "Applicable model values diverge materially; review assumptions."
        confidence_multiplier = 0.8
    return (
        ValuationPerspective(
            name="Multi-Model Fair Value",
            pessimistic=round(pessimistic, 2),
            base=round(base, 2),
            optimistic=round(optimistic, 2),
            applicability=", ".join(str(item["model"]) for item in components),
            warning=warning,
        ),
        components,
        confidence_multiplier,
    )


def safety_label(margin: float) -> str:
    if margin > 0.30:
        return "Substantial"
    if margin >= 0.20:
        return "Attractive"
    if margin >= 0.10:
        return "Moderately undervalued"
    if margin >= -0.10:
        return "Near fair value"
    if margin >= -0.30:
        return "Moderately overvalued"
    return "Substantially overvalued"


def run_valuation(data: ValuationInput) -> ValuationResult:
    reported_fcf = data.operating_cash_flow - data.capex - data.finance_lease_principal
    owner_earnings = data.sustainable_owner_earnings
    warning = None
    confidence = data.confidence
    if owner_earnings is None:
        maintenance = data.maintenance_capex
        if maintenance is None:
            maintenance = data.capex
            warning = "Maintenance/growth CapEx split unavailable; confidence reduced."
            confidence *= 0.7
        owner_earnings = data.operating_cash_flow - maintenance - data.finance_lease_principal

    strict, strict_terminal = _perspective(
        "Strict FCF Value", reported_fcf, data, "reported cash expenditure"
    )
    normalised, owner_terminal = _perspective(
        "Normalised Owner Earnings Value",
        owner_earnings,
        data,
        "maintenance economics",
        warning,
    )
    blended_cash_flow = (reported_fcf * 0.4) + (owner_earnings * 0.6)
    blended_dcf, multi_terminal = _perspective(
        "Blended Cash-Flow DCF",
        blended_cash_flow,
        data,
        "cash-flow cross-check",
    )
    multi, model_components, model_confidence_multiplier = _multi_model_perspective(
        data,
        reported_fcf=reported_fcf,
        blended_dcf_value=blended_dcf.base,
    )
    margin = (multi.base - data.market_price) / multi.base if multi.base else -1
    sensitivity: list[dict[str, float]] = []
    for discount_delta in (-0.01, 0, 0.01):
        value, _ = _dcf_per_share(
            blended_cash_flow,
            data.growth_rate,
            data.terminal_growth,
            data.discount_rate + discount_delta,
            data.forecast_years,
            data.net_cash,
            data.diluted_shares,
        )
        sensitivity.append(
            {
                "discount_rate": round(data.discount_rate + discount_delta, 4),
                "terminal_growth": data.terminal_growth,
                "value": round(value, 2),
            }
        )
    terminal_max = max(strict_terminal, owner_terminal, multi_terminal)
    if terminal_max > 0.8:
        confidence *= 0.85
    confidence *= model_confidence_multiplier

    return ValuationResult(
        symbol=data.symbol,
        provenance=data.provenance,
        strict_fcf=strict,
        normalised_owner_earnings=normalised,
        multi_model_fair_value=multi,
        safety_margin=round(margin, 4),
        safety_label=safety_label(margin),
        confidence=round(max(0, min(1, confidence)), 3),
        assumptions={
            "growth_rate": data.growth_rate,
            "terminal_growth": data.terminal_growth,
            "discount_rate": data.discount_rate,
            "forecast_years": data.forecast_years,
            "reported_fcf": reported_fcf,
            "owner_earnings": owner_earnings,
            "revenue": data.revenue,
            "ebitda": data.ebitda,
            "net_income": data.net_income,
            "ev_revenue_multiple": data.ev_revenue_multiple,
            "ev_ebitda_multiple": data.ev_ebitda_multiple,
            "pe_multiple": data.pe_multiple,
            "p_fcf_multiple": data.p_fcf_multiple,
            "terminal_value_share_max": round(terminal_max, 4),
            "source": data.source,
        },
        model_components=model_components,
        sensitivity=sensitivity,
        calculation_version=CALCULATION_VERSION,
        calculated_at=datetime.now(UTC),
    )
