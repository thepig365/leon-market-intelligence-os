"""Convert official SEC filings into versioned LMIO news events."""

import json
from datetime import UTC, datetime
from hashlib import sha256

from lmio.domain import NewsEvent
from lmio.news import event_fingerprint
from lmio.providers.sec import SECProvider
from lmio.sec_ownership import parse_ownership_filing
from lmio.store import RuntimeStore

SIGNIFICANT_FORMS = {
    "8-K",
    "10-K",
    "10-Q",
    "13F-HR",
    "13F-HR/A",
    "SC 13D",
    "SC 13D/A",
    "SC 13G",
    "SC 13G/A",
    "13D",
    "13D/A",
    "13G",
    "13G/A",
    "4",
    "4/A",
}
OWNERSHIP_FORMS = SIGNIFICANT_FORMS - {"8-K", "10-K", "10-Q"}


def filing_url(filing: dict[str, str]) -> str:
    cik = filing["cik"].lstrip("0")
    accession = filing["accession_number"].replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{filing['primary_document']}"


def monitor_sec(
    provider: SECProvider,
    store: RuntimeStore,
    watchlist: dict[str, str],
    *,
    max_per_symbol: int = 25,
) -> dict[str, int]:
    inserted = 0
    ownership_inserted = 0
    checked = 0
    for symbol, cik in sorted(watchlist.items()):
        for filing in provider.recent_filings(cik)[:max_per_symbol]:
            checked += 1
            form = str(filing["form"])
            event = NewsEvent(
                headline=f"{symbol} filed SEC Form {form}",
                source="SEC EDGAR",
                source_url=filing_url(filing),
                source_tier=1,
                published_at=datetime.fromisoformat(str(filing["filing_date"])).replace(tzinfo=UTC),
                symbols=[symbol],
                event_type=f"sec_{form.lower().replace('/', '_')}",
                significance=80 if form in SIGNIFICANT_FORMS else 40,
                surprise=0,
                confidence=1,
            )
            was_inserted = store.put_news_event(
                event_fingerprint(event),
                event.model_dump(mode="json"),
            )
            if was_inserted:
                inserted += 1
            filing_fingerprint = sha256(f"ownership-filing:{event.source_url}".encode()).hexdigest()
            if form in OWNERSHIP_FORMS and not store.has_ingestion_fingerprint(filing_fingerprint):
                document_url = provider.ownership_document_url(filing)
                document = provider.fetch_document(document_url)
                for index, parsed in enumerate(
                    parse_ownership_filing(form, document, document_url)
                ):
                    payload = parsed.model_dump(mode="json")
                    fingerprint = sha256(
                        json.dumps(
                            {
                                "source_url": event.source_url,
                                "document_url": document_url,
                                "index": index,
                                "payload": payload,
                            },
                            sort_keys=True,
                        ).encode()
                    ).hexdigest()
                    if store.put_ownership_event(
                        fingerprint,
                        symbol=symbol,
                        event_type=classify_ownership_event(form),
                        source_url=document_url,
                        payload=payload,
                    ):
                        ownership_inserted += 1
                store.mark_ingestion_fingerprint(
                    filing_fingerprint,
                    "ownership_filing",
                )
    return {
        "symbols": len(watchlist),
        "checked": checked,
        "inserted": inserted,
        "ownership_inserted": ownership_inserted,
    }


def classify_ownership_event(form: str) -> str:
    normalised = form.upper()
    if normalised.startswith("13F"):
        return "institutional_holdings"
    if normalised in {"4", "4/A"}:
        return "insider_transaction"
    return "beneficial_ownership"
