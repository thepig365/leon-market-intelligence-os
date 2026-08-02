"""Convert official SEC filings into versioned LMIO news events."""

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.error import HTTPError

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
) -> dict[str, object]:
    inserted = 0
    ownership_inserted = 0
    checked = 0
    succeeded = 0
    skipped = 0
    failed = 0
    failures: list[dict[str, object]] = []
    for symbol, cik in sorted(watchlist.items()):
        try:
            filings = provider.recent_filings(cik)[:max_per_symbol]
        except Exception as error:
            failed += 1
            failure = _failure_record(symbol, cik, None, error, retry_count=0)
            failures.append(failure)
            store.append_json(
                "system_events",
                {
                    "event_type": "sec_provider_failure",
                    "severity": "error",
                    "payload": failure,
                },
            )
            continue
        for filing in filings:
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
            if form not in OWNERSHIP_FORMS:
                succeeded += 1
                continue
            if store.has_ingestion_fingerprint(filing_fingerprint):
                skipped += 1
                continue

            last_error: Exception | None = None
            for _retry_count in range(3):
                try:
                    document_url = provider.ownership_document_url(filing)
                    document = provider.fetch_document(document_url)
                    parsed_records = parse_ownership_filing(form, document, document_url)
                    for index, parsed in enumerate(parsed_records):
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
                    succeeded += 1
                    last_error = None
                    break
                except Exception as error:
                    last_error = error
            if last_error is not None:
                failed += 1
                failure = _failure_record(symbol, cik, filing, last_error, retry_count=3)
                failures.append(failure)
                store.append_json(
                    "system_events",
                    {
                        "event_type": "sec_filing_failure",
                        "severity": "warning",
                        "payload": failure,
                    },
                )
    status = "succeeded"
    if failed and succeeded:
        status = "partial"
    elif failed:
        status = "failed"
    return {
        "status": status,
        "symbols": len(watchlist),
        "attempted": checked,
        "checked": checked,
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": failed,
        "inserted": inserted,
        "ownership_inserted": ownership_inserted,
        "failures": failures,
    }


def _failure_record(
    symbol: str,
    cik: str,
    filing: dict[str, str] | None,
    error: Exception,
    *,
    retry_count: int,
) -> dict[str, object]:
    attempted_at = datetime.now(UTC)
    accession = filing.get("accession_number") if filing else None
    url = (
        filing_url(filing)
        if filing
        else f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    )
    if isinstance(error, HTTPError):
        http_result: int | None = error.code
        category = "fair_access_rejection" if error.code in {403, 429} else "http_error"
    elif isinstance(error, TimeoutError):
        http_result = None
        category = "timeout"
    elif isinstance(error, (ValueError, json.JSONDecodeError)):
        http_result = None
        category = "parser_failure"
    else:
        http_result = None
        category = "provider_or_transport_failure"
    fingerprint = sha256(
        f"{symbol}:{accession}:{url}:{category}:{type(error).__name__}".encode()
    ).hexdigest()
    return {
        "failure_fingerprint": fingerprint,
        "symbol": symbol,
        "accession_number": accession,
        "filing_url": url,
        "attempted_at": attempted_at.isoformat(),
        "status": "failed",
        "http_result": http_result,
        "failure_category": category,
        "error_type": type(error).__name__,
        "retry_count": retry_count,
        "next_retry_at": (attempted_at + timedelta(minutes=15 * max(1, retry_count))).isoformat(),
    }


def classify_ownership_event(form: str) -> str:
    normalised = form.upper()
    if normalised.startswith("13F"):
        return "institutional_holdings"
    if normalised in {"4", "4/A"}:
        return "insider_transaction"
    return "beneficial_ownership"
