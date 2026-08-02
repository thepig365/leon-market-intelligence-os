"""Company-type valuation routing without applying inappropriate models."""

from enum import StrEnum

from pydantic import BaseModel, Field


class CompanyType(StrEnum):
    STABLE_PROFITABLE = "stable_profitable"
    HIGH_GROWTH_TECHNOLOGY = "high_growth_technology"
    BANK_INSURANCE = "bank_insurance"
    REIT = "reit"
    CYCLICAL = "cyclical"
    UNPROFITABLE = "unprofitable"
    RESOURCE = "resource"
    MATURE_DIVIDEND = "mature_dividend"
    SPECIAL_SITUATION = "special_situation"


class ModelRoute(BaseModel):
    company_type: CompanyType
    preferred_models: list[str]
    supported_in_v1_engine: bool
    warning: str | None = None
    not_applicable_reason: str | None = None
    required_alternative_method: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


ROUTES = {
    CompanyType.STABLE_PROFITABLE: ["FCFF/FCFE DCF"],
    CompanyType.HIGH_GROWTH_TECHNOLOGY: ["Revenue-to-margin DCF", "multiples"],
    CompanyType.BANK_INSURANCE: ["Residual income", "DDM", "P/B"],
    CompanyType.REIT: ["AFFO/FFO", "NAV"],
    CompanyType.CYCLICAL: ["Normalised earnings", "EV/EBITDA"],
    CompanyType.UNPROFITABLE: ["Revenue scenarios"],
    CompanyType.RESOURCE: ["NAV", "commodity-price scenarios"],
    CompanyType.MATURE_DIVIDEND: ["DDM", "FCFE"],
    CompanyType.SPECIAL_SITUATION: ["Deal value", "break value"],
}


def route_models(company_type: CompanyType) -> ModelRoute:
    supported = company_type in {
        CompanyType.STABLE_PROFITABLE,
        CompanyType.HIGH_GROWTH_TECHNOLOGY,
    }
    warning = None
    if not supported:
        warning = (
            "The current cash-flow engine must not be used for this company type; "
            "route to a specialised model before publishing a value."
        )
    return ModelRoute(
        company_type=company_type,
        preferred_models=ROUTES[company_type],
        supported_in_v1_engine=supported,
        warning=warning,
        not_applicable_reason=(
            None
            if supported
            else "Generic cash-flow assumptions do not represent this company's economics."
        ),
        required_alternative_method=[] if supported else ROUTES[company_type],
        missing_evidence=(
            []
            if supported
            else ["specialised_model_inputs", "independent_model_review"]
        ),
    )
