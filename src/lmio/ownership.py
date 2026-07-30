"""Basic official-filing classification for institutional and insider evidence."""

from enum import StrEnum

from pydantic import BaseModel


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
