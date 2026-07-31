"""Basic official-filing classification for institutional and insider evidence."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class OwnershipEvidenceType(StrEnum):
    INSIDER_TRANSACTION = "insider_transaction"
    ACTIVIST_OR_BENEFICIAL_OWNER = "activist_or_beneficial_owner"
    INSTITUTIONAL_HOLDINGS = "institutional_holdings"
    OTHER = "other"


class OwnershipEvidence(BaseModel):
    form: str
    evidence_type: OwnershipEvidenceType
    source_url: str
    interpretation_limit: str


class InsiderTransaction(BaseModel):
    symbol: str
    insider: str
    transaction_date: date
    transaction_code: str
    shares: float = Field(gt=0)
    price: float = Field(ge=0)
    direct_ownership: bool
    source_url: str


class InsiderBuyingSummary(BaseModel):
    symbol: str
    open_market_purchase_value: float
    purchaser_count: int
    cluster_purchase: bool
    evidence_urls: list[str]
    interpretation_limit: str


def summarise_insider_buying(
    transactions: list[InsiderTransaction],
) -> InsiderBuyingSummary | None:
    purchases = [
        item
        for item in transactions
        if item.transaction_code.upper() == "P" and item.direct_ownership
    ]
    if not purchases:
        return None
    symbols = {item.symbol.upper() for item in purchases}
    if len(symbols) != 1:
        raise ValueError("insider summary requires one symbol")
    purchasers = {item.insider.strip().lower() for item in purchases}
    dates = [item.transaction_date for item in purchases]
    within_cluster_window = (max(dates) - min(dates)).days <= 30
    return InsiderBuyingSummary(
        symbol=next(iter(symbols)),
        open_market_purchase_value=round(
            sum(item.shares * item.price for item in purchases),
            2,
        ),
        purchaser_count=len(purchasers),
        cluster_purchase=len(purchasers) >= 2 and within_cluster_window,
        evidence_urls=sorted({item.source_url for item in purchases}),
        interpretation_limit=(
            "Open-market purchases are supporting evidence only; grants, "
            "option exercises and indirect changes are excluded."
        ),
    )


class ActivistAssessment(BaseModel):
    stake_pct: float = Field(ge=0, le=100)
    intent_disclosed: bool
    catalyst_language_found: bool
    eligible_supporting_factor: bool
    warning: str


def assess_activist_filing(stake_pct: float, purpose_text: str) -> ActivistAssessment:
    normalised = purpose_text.lower()
    catalysts = (
        "strategic alternatives",
        "board representation",
        "sale of the company",
        "operational improvements",
    )
    catalyst_found = any(term in normalised for term in catalysts)
    intent_disclosed = bool(normalised.strip())
    return ActivistAssessment(
        stake_pct=stake_pct,
        intent_disclosed=intent_disclosed,
        catalyst_language_found=catalyst_found,
        eligible_supporting_factor=stake_pct >= 5 and catalyst_found,
        warning=(
            "A 13D is a supporting catalyst only; position, purpose, amendments "
            "and price confirmation still require review."
        ),
    )


def classify_filing(form: str, source_url: str) -> OwnershipEvidence:
    normalised = form.upper().strip()
    if normalised in {"4", "4/A"}:
        evidence_type = OwnershipEvidenceType.INSIDER_TRANSACTION
        limit = "A Form 4 filing is evidence of a transaction, not automatically a bullish signal."
    elif normalised in {"SC 13D", "SC 13D/A", "13D", "13D/A", "13G", "13G/A"}:
        evidence_type = OwnershipEvidenceType.ACTIVIST_OR_BENEFICIAL_OWNER
        limit = "Ownership disclosure requires position, intent and amendment review."
    elif normalised in {"13F-HR", "13F-HR/A"}:
        evidence_type = OwnershipEvidenceType.INSTITUTIONAL_HOLDINGS
        limit = "13F data is delayed and is a confirmation factor, not the main engine."
    else:
        evidence_type = OwnershipEvidenceType.OTHER
        limit = "No ownership interpretation is inferred from this form."
    return OwnershipEvidence(
        form=normalised,
        evidence_type=evidence_type,
        source_url=source_url,
        interpretation_limit=limit,
    )
