"""Convert official SEC filings into versioned LMIO news events."""

from datetime import UTC, datetime

from lmio.domain import NewsEvent
from lmio.news import event_fingerprint
from lmio.providers.sec import SECProvider
from lmio.store import RuntimeStore

SIGNIFICANT_FORMS = {"8-K", "10-K", "10-Q", "13D", "13D/A", "13G", "13G/A", "4"}


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
            if store.put_news_event(
                event_fingerprint(event),
                event.model_dump(mode="json"),
            ):
                inserted += 1
    return {"symbols": len(watchlist), "checked": checked, "inserted": inserted}
