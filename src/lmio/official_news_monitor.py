"""Persist deduplicated events from approved official macroeconomic feeds."""

from lmio.news import deduplicate_events, event_fingerprint
from lmio.providers.official_rss import OfficialRSSProvider
from lmio.store import RuntimeStore


def monitor_official_news(
    provider: OfficialRSSProvider,
    store: RuntimeStore,
) -> dict[str, int]:
    raw_events, failures = provider.collect_events()
    if failures and len(failures) == len(provider.feeds):
        raise RuntimeError("all official news feeds failed safely")
    events = deduplicate_events(raw_events)
    inserted = 0
    for event in events:
        if store.put_news_event(event_fingerprint(event), event.model_dump(mode="json")):
            inserted += 1
    return {
        "feeds": len(provider.feeds),
        "failed_feeds": len(failures),
        "checked": len(events),
        "inserted": inserted,
    }
