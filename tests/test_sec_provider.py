import json

from lmio.providers import ProviderState
from lmio.providers.sec import SECProvider


def test_sec_is_disabled_without_fair_access_identity() -> None:
    assert SECProvider("").health().state is ProviderState.DISABLED


def test_sec_contract_normalises_recent_filings() -> None:
    payload = {
        "cik": "320193",
        "filings": {
            "recent": {
                "accessionNumber": ["0001"],
                "filingDate": ["2026-01-01"],
                "form": ["8-K"],
                "primaryDocument": ["report.htm"],
            }
        },
    }
    captured: dict[str, object] = {}

    def transport(url: str, headers: dict[str, str]) -> bytes:
        captured.update({"url": url, "headers": headers})
        return json.dumps(payload).encode()

    provider = SECProvider("LMIO research admin@example.test", transport)

    assert provider.health().state is ProviderState.READY
    assert provider.recent_filings("320193") == [
        {
            "accession_number": "0001",
            "filing_date": "2026-01-01",
            "form": "8-K",
            "primary_document": "report.htm",
            "source": "SEC EDGAR",
        }
    ]
    assert captured["headers"]["User-Agent"] == "LMIO research admin@example.test"


def test_sec_contract_rejects_missing_fields() -> None:
    def transport(_url: str, _headers: dict[str, str]) -> bytes:
        return json.dumps({"cik": "1", "filings": {"recent": {}}}).encode()

    provider = SECProvider("LMIO research admin@example.test", transport)

    try:
        provider.recent_filings("1")
    except ValueError as error:
        assert "incomplete" in str(error)
    else:
        raise AssertionError("incomplete SEC response should fail")
