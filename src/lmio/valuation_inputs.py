"""Provider-neutral, fail-closed preparation of reproducible valuation inputs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from lmio.domain import DataProvenance, ValuationInput


class FinancialEvidence(BaseModel):
    symbol: str
    company_type: str = "operating_company"
    provenance: DataProvenance
    observed_at: datetime
    source_fields: dict[str, float | None]
    source_references: dict[str, str]
    assumptions: dict[str, float | int]


class PreparedValuationInput(BaseModel):
    symbol: str
    status: Literal["ready", "blocked", "unsupported"]
    route: str
    model_version: str = "valuation-input-builder-v1"
    source_fields: dict[str, float | None]
    source_references: dict[str, str]
    derived_calculations: dict[str, float]
    assumptions: dict[str, float | int]
    missing_fields: list[str] = Field(default_factory=list)
    valuation_input: ValuationInput | None = None


REQUIRED_FIELDS = (
    "operating_cash_flow",
    "capex",
    "net_cash",
    "diluted_shares",
    "market_price",
)
REQUIRED_ASSUMPTIONS = (
    "growth_rate",
    "terminal_growth",
    "discount_rate",
    "forecast_years",
)
UNSUPPORTED_COMPANY_TYPES = {"bank", "insurer", "reit", "pre_revenue"}


def prepare_valuation_input(evidence: FinancialEvidence) -> PreparedValuationInput:
    """Prepare a valuation input without filling any absent fact or assumption."""

    if not evidence.provenance.operational:
        return PreparedValuationInput(
            symbol=evidence.symbol,
            status="blocked",
            route="non_operational_provenance",
            source_fields=evidence.source_fields,
            source_references=evidence.source_references,
            derived_calculations={},
            assumptions=evidence.assumptions,
            missing_fields=["operational provenance"],
        )
    if evidence.company_type.lower() in UNSUPPORTED_COMPANY_TYPES:
        return PreparedValuationInput(
            symbol=evidence.symbol,
            status="unsupported",
            route=f"specialist_model_required:{evidence.company_type.lower()}",
            source_fields=evidence.source_fields,
            source_references=evidence.source_references,
            derived_calculations={},
            assumptions=evidence.assumptions,
        )

    missing = [name for name in REQUIRED_FIELDS if evidence.source_fields.get(name) is None]
    missing.extend(name for name in REQUIRED_ASSUMPTIONS if evidence.assumptions.get(name) is None)
    if missing:
        return PreparedValuationInput(
            symbol=evidence.symbol,
            status="blocked",
            route="missing_required_inputs",
            source_fields=evidence.source_fields,
            source_references=evidence.source_references,
            derived_calculations={},
            assumptions=evidence.assumptions,
            missing_fields=missing,
        )

    fields = evidence.source_fields
    assumptions = evidence.assumptions
    finance_lease_principal = fields.get("finance_lease_principal") or 0
    strict_fcf = (
        float(fields["operating_cash_flow"]) - float(fields["capex"]) - finance_lease_principal
    )
    valuation_input = ValuationInput(
        symbol=evidence.symbol,
        provenance=evidence.provenance,
        operating_cash_flow=float(fields["operating_cash_flow"]),
        capex=float(fields["capex"]),
        finance_lease_principal=finance_lease_principal,
        maintenance_capex=fields.get("maintenance_capex"),
        growth_capex=fields.get("growth_capex"),
        sustainable_owner_earnings=fields.get("sustainable_owner_earnings"),
        revenue=fields.get("revenue"),
        ebitda=fields.get("ebitda"),
        net_income=fields.get("net_income"),
        ev_revenue_multiple=fields.get("ev_revenue_multiple"),
        ev_ebitda_multiple=fields.get("ev_ebitda_multiple"),
        pe_multiple=fields.get("pe_multiple"),
        p_fcf_multiple=fields.get("p_fcf_multiple"),
        net_cash=float(fields["net_cash"]),
        diluted_shares=float(fields["diluted_shares"]),
        growth_rate=float(assumptions["growth_rate"]),
        terminal_growth=float(assumptions["terminal_growth"]),
        discount_rate=float(assumptions["discount_rate"]),
        forecast_years=int(assumptions["forecast_years"]),
        market_price=float(fields["market_price"]),
        source="; ".join(sorted(set(evidence.source_references.values()))),
        observed_at=evidence.observed_at,
        confidence=float(assumptions.get("confidence", 0.8)),
    )
    return PreparedValuationInput(
        symbol=evidence.symbol,
        status="ready",
        route="standard_operating_company",
        source_fields=evidence.source_fields,
        source_references=evidence.source_references,
        derived_calculations={"strict_fcf": strict_fcf},
        assumptions=evidence.assumptions,
        valuation_input=valuation_input,
    )
