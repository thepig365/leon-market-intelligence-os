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
            "cik": "0000320193",
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


def test_sec_document_fetch_rejects_non_sec_hosts() -> None:
    provider = SECProvider("LMIO research admin@example.test", lambda *_: b"")

    try:
        provider.fetch_document("https://example.com/filing.xml")
    except ValueError as error:
        assert "approved sec.gov" in str(error)
    else:
        raise AssertionError("non-SEC document host should fail closed")


def test_sec_document_fetch_uses_fair_access_identity() -> None:
    captured: dict[str, object] = {}

    def transport(url: str, headers: dict[str, str]) -> bytes:
        captured.update({"url": url, "headers": headers})
        return b"<ownershipDocument />"

    provider = SECProvider("LMIO research admin@example.test", transport)
    url = "https://www.sec.gov/Archives/edgar/data/1/2/form4.xml"

    assert provider.fetch_document(url) == "<ownershipDocument />"
    assert captured == {
        "url": url,
        "headers": {
            "User-Agent": "LMIO research admin@example.test",
            "Host": "www.sec.gov",
        },
    }


def test_13f_information_table_url_is_resolved_from_official_directory() -> None:
    directory = {
        "directory": {
            "item": [
                {"name": "primary_doc.xml"},
                {"name": "information_table.xml"},
            ]
        }
    }

    def transport(_url: str, _headers: dict[str, str]) -> bytes:
        return json.dumps(directory).encode()

    provider = SECProvider("LMIO research admin@example.test", transport)
    filing = {
        "cik": "0001652044",
        "accession_number": "0001652044-25-000096",
        "form": "13F-HR",
        "primary_document": "primary_doc.xml",
    }

    assert provider.ownership_document_url(filing) == (
        "https://www.sec.gov/Archives/edgar/data/1652044/000165204425000096/information_table.xml"
    )
