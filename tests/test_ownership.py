from lmio.ownership import OwnershipEvidenceType, classify_filing


def test_form4_is_not_automatically_bullish() -> None:
    evidence = classify_filing("4", "https://www.sec.gov/example")

    assert evidence.evidence_type is OwnershipEvidenceType.INSIDER_TRANSACTION
    assert "not automatically a bullish signal" in evidence.interpretation_limit


def test_13f_is_delayed_confirmation_only() -> None:
    evidence = classify_filing("13F-HR", "https://www.sec.gov/example")

    assert evidence.evidence_type is OwnershipEvidenceType.INSTITUTIONAL_HOLDINGS
    assert "delayed" in evidence.interpretation_limit
