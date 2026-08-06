from datetime import date

from lmio.ownership import (
    InsiderTransaction,
    OwnershipEvidenceType,
    assess_activist_filing,
    classify_filing,
    summarise_insider_buying,
)


def test_form4_is_not_automatically_bullish() -> None:
    evidence = classify_filing("4", "https://www.sec.gov/example")

    assert evidence.evidence_type is OwnershipEvidenceType.INSIDER_TRANSACTION
    assert "not automatically a bullish signal" in evidence.interpretation_limit


def test_13f_is_delayed_confirmation_only() -> None:
    evidence = classify_filing("13F-HR", "https://www.sec.gov/example")

    assert evidence.evidence_type is OwnershipEvidenceType.INSTITUTIONAL_HOLDINGS
    assert "delayed" in evidence.interpretation_limit


def test_form4_summary_excludes_non_purchase_codes_and_detects_cluster() -> None:
    transactions = [
        InsiderTransaction(
            symbol="TEST",
            insider="A",
            transaction_date=date(2026, 7, 1),
            transaction_code="P",
            shares=100,
            price=10,
            direct_ownership=True,
            source_url="https://www.sec.gov/a",
        ),
        InsiderTransaction(
            symbol="TEST",
            insider="B",
            transaction_date=date(2026, 7, 2),
            transaction_code="P",
            shares=200,
            price=10,
            direct_ownership=True,
            source_url="https://www.sec.gov/b",
        ),
        InsiderTransaction(
            symbol="TEST",
            insider="C",
            transaction_date=date(2026, 7, 2),
            transaction_code="A",
            shares=1000,
            price=0,
            direct_ownership=True,
            source_url="https://www.sec.gov/c",
        ),
    ]

    summary = summarise_insider_buying(transactions)

    assert summary is not None
    assert summary.cluster_purchase is True
    assert summary.open_market_purchase_value == 3000


def test_activist_stake_needs_disclosed_catalyst_language() -> None:
    passive = assess_activist_filing(8, "The investor acquired the shares.")
    active = assess_activist_filing(8, "The investor seeks board representation.")

    assert passive.eligible_supporting_factor is False
    assert active.eligible_supporting_factor is True
