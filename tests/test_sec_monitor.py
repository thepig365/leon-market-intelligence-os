import json
from pathlib import Path

from lmio.providers.sec import SECProvider
from lmio.sec_monitor import monitor_sec
from lmio.store import RuntimeStore


def test_monitor_persists_official_filings_once(tmp_path: Path) -> None:
    response = {
        "cik": "320193",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-26-000001"],
                "filingDate": ["2026-01-02"],
                "form": ["8-K"],
                "primaryDocument": ["report.htm"],
            }
        },
    }

    def transport(_url: str, _headers: dict[str, str]) -> bytes:
        return json.dumps(response).encode()

    provider = SECProvider("LMIO admin@example.test", transport)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()

    first = monitor_sec(provider, store, {"AAPL": "320193"})
    second = monitor_sec(provider, store, {"AAPL": "320193"})

    assert first == {
        "status": "succeeded",
        "symbols": 1,
        "attempted": 1,
        "checked": 1,
        "succeeded": 1,
        "skipped": 0,
        "failed": 0,
        "inserted": 1,
        "ownership_inserted": 0,
        "failures": [],
    }
    assert second == {
        "status": "succeeded",
        "symbols": 1,
        "attempted": 1,
        "checked": 1,
        "succeeded": 1,
        "skipped": 0,
        "failed": 0,
        "inserted": 0,
        "ownership_inserted": 0,
        "failures": [],
    }
    assert store.counts()["news_events"] == 1


def test_monitor_parses_and_deduplicates_form4_transactions(tmp_path: Path) -> None:
    submissions = {
        "cik": "1",
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001"],
                "filingDate": ["2026-07-30"],
                "form": ["4"],
                "primaryDocument": ["form4.xml"],
            }
        },
    }
    form4 = """
    <ownershipDocument>
      <issuer>
        <issuerName>Example Corp</issuerName>
        <issuerTradingSymbol>TEST</issuerTradingSymbol>
      </issuer>
      <reportingOwner>
        <reportingOwnerId><rptOwnerName>Example Insider</rptOwnerName></reportingOwnerId>
      </reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionDate><value>2026-07-29</value></transactionDate>
          <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>100</value></transactionShares>
            <transactionPricePerShare><value>10</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
          <ownershipNature>
            <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
          </ownershipNature>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
    </ownershipDocument>
    """

    def transport(url: str, _headers: dict[str, str]) -> bytes:
        if url.startswith("https://data.sec.gov/"):
            return json.dumps(submissions).encode()
        return form4.encode()

    provider = SECProvider("LMIO admin@example.test", transport)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()

    first = monitor_sec(provider, store, {"TEST": "1"})
    second = monitor_sec(provider, store, {"TEST": "1"})

    assert first["ownership_inserted"] == 1
    assert second["ownership_inserted"] == 0
    records = store.history_json("ownership_events")
    assert len(records) == 1
    assert records[0]["event_type"] == "insider_transaction"
    assert records[0]["payload"]["transaction_code"] == "P"


def test_monitor_backfills_structured_ownership_for_existing_news(tmp_path: Path) -> None:
    submissions = {
        "cik": "1",
        "filings": {
            "recent": {
                "accessionNumber": ["0000000001-26-000001"],
                "filingDate": ["2026-07-30"],
                "form": ["4"],
                "primaryDocument": ["form4.xml"],
            }
        },
    }
    form4 = """
    <ownershipDocument>
      <issuer>
        <issuerName>Example Corp</issuerName>
        <issuerTradingSymbol>TEST</issuerTradingSymbol>
      </issuer>
      <reportingOwner>
        <reportingOwnerId><rptOwnerName>Example Insider</rptOwnerName></reportingOwnerId>
      </reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionDate><value>2026-07-29</value></transactionDate>
          <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>100</value></transactionShares>
            <transactionPricePerShare><value>10</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
          <ownershipNature>
            <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
          </ownershipNature>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
    </ownershipDocument>
    """
    fetched_documents = 0

    def transport(url: str, _headers: dict[str, str]) -> bytes:
        nonlocal fetched_documents
        if url.startswith("https://data.sec.gov/"):
            return json.dumps(submissions).encode()
        fetched_documents += 1
        return form4.encode()

    provider = SECProvider("LMIO admin@example.test", transport)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()

    first = monitor_sec(provider, store, {"TEST": "1"})
    with store.connection() as connection:
        connection.execute("DELETE FROM ownership_events")
        connection.execute(
            "DELETE FROM ingestion_dedup WHERE record_type IN "
            "('ownership_event', 'ownership_filing')"
        )

    backfill = monitor_sec(provider, store, {"TEST": "1"})
    no_repeat = monitor_sec(provider, store, {"TEST": "1"})

    assert first["inserted"] == 1
    assert backfill["inserted"] == 0
    assert backfill["ownership_inserted"] == 1
    assert no_repeat["ownership_inserted"] == 0
    assert fetched_documents == 2
    assert store.counts()["ownership_events"] == 1


def test_monitor_resolves_and_parses_13f_information_table(tmp_path: Path) -> None:
    submissions = {
        "cik": "1652044",
        "filings": {
            "recent": {
                "accessionNumber": ["0001652044-25-000096"],
                "filingDate": ["2025-11-06"],
                "form": ["13F-HR"],
                "primaryDocument": ["primary_doc.xml"],
            }
        },
    }
    directory = {
        "directory": {
            "item": [
                {"name": "primary_doc.xml"},
                {"name": "information_table.xml"},
            ]
        }
    }
    information_table = """
    <informationTable>
      <infoTable>
        <nameOfIssuer>Example Corp</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>123456789</cusip>
        <value>125000</value>
        <shrsOrPrnAmt>
          <sshPrnamt>1000</sshPrnamt>
          <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
        <votingAuthority><Sole>1000</Sole><Shared>0</Shared><None>0</None></votingAuthority>
      </infoTable>
    </informationTable>
    """

    def transport(url: str, _headers: dict[str, str]) -> bytes:
        if url.startswith("https://data.sec.gov/"):
            return json.dumps(submissions).encode()
        if url.endswith("/index.json"):
            return json.dumps(directory).encode()
        if url.endswith("/information_table.xml"):
            return information_table.encode()
        raise AssertionError(f"unexpected SEC URL: {url}")

    provider = SECProvider("LMIO admin@example.test", transport)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()

    result = monitor_sec(provider, store, {"GOOG": "1652044"})

    assert result["ownership_inserted"] == 1
    records = store.history_json("ownership_events")
    assert records[0]["event_type"] == "institutional_holdings"
    assert records[0]["payload"]["value_usd"] == 125_000
    assert records[0]["source_url"].endswith("/information_table.xml")


def test_one_failing_filing_does_not_abort_valid_filings(tmp_path: Path) -> None:
    submissions = {
        "cik": "1",
        "filings": {
            "recent": {
                "accessionNumber": ["bad-accession", "good-accession"],
                "filingDate": ["2026-07-30", "2026-07-30"],
                "form": ["4", "4"],
                "primaryDocument": ["bad.xml", "good.xml"],
            }
        },
    }
    valid_form = """
    <ownershipDocument>
      <issuer>
        <issuerName>Good Corp</issuerName><issuerTradingSymbol>GOOD</issuerTradingSymbol>
      </issuer>
      <reportingOwner>
        <reportingOwnerId><rptOwnerName>Owner</rptOwnerName></reportingOwnerId>
      </reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionDate><value>2026-07-29</value></transactionDate>
          <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>10</value></transactionShares>
            <transactionPricePerShare><value>5</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
          <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
    </ownershipDocument>
    """

    def transport(url: str, _headers: dict[str, str]) -> bytes:
        if url.startswith("https://data.sec.gov/"):
            return json.dumps(submissions).encode()
        if url.endswith("/bad.xml"):
            raise TimeoutError("one filing timed out")
        return valid_form.encode()

    provider = SECProvider("LMIO admin@example.test", transport)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()

    result = monitor_sec(provider, store, {"TEST": "1"})

    assert result["status"] == "partial"
    assert result["attempted"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert result["ownership_inserted"] == 1
    assert result["failures"][0]["failure_category"] == "timeout"
    assert result["failures"][0]["retry_count"] == 3
    failures = [
        item
        for item in store.history_json("system_events")
        if item["event_type"] == "sec_filing_failure"
    ]
    assert failures[0]["payload"]["failure_fingerprint"]
