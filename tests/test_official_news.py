from datetime import UTC, datetime
from pathlib import Path

import pytest

from lmio.official_news_monitor import monitor_official_news
from lmio.providers.official_rss import OfficialFeed, OfficialRSSProvider
from lmio.store import RuntimeStore

FEED = OfficialFeed(
    name="test_feed",
    url="https://www.bls.gov/feed/test.rss",
    source="U.S. Bureau of Labor Statistics",
    event_type="macro_test",
    significance=90,
)


def rss(link: str = "https://www.bls.gov/news.release/test.htm") -> bytes:
    return f"""
    <rss version="2.0"><channel><title>Official</title><item>
      <title>Employment Situation released</title>
      <link>{link}</link>
      <pubDate>Fri, 31 Jul 2026 08:30:00 -0400</pubDate>
    </item></channel></rss>
    """.encode()


def test_official_feed_normalises_market_event() -> None:
    provider = OfficialRSSProvider((FEED,), lambda *_: rss())

    event = provider.events()[0]

    assert event.symbols == []
    assert event.source_tier == 1
    assert event.event_type == "macro_test"
    assert event.published_at == datetime(2026, 7, 31, 12, 30, tzinfo=UTC)


def test_official_feed_rejects_non_official_item_link() -> None:
    provider = OfficialRSSProvider((FEED,), lambda *_: rss("https://example.com/story"))

    assert provider.events() == []


def test_official_feed_rejects_unapproved_feed_host() -> None:
    provider = OfficialRSSProvider(
        (
            OfficialFeed(
                name="bad",
                url="https://example.com/feed.xml",
                source="Example",
                event_type="test",
                significance=80,
            ),
        ),
        lambda *_: rss(),
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        provider.events()


def test_official_monitor_persists_each_release_once(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()
    provider = OfficialRSSProvider((FEED,), lambda *_: rss())

    assert monitor_official_news(provider, store) == {
        "feeds": 1,
        "failed_feeds": 0,
        "checked": 1,
        "inserted": 1,
    }
    assert monitor_official_news(provider, store) == {
        "feeds": 1,
        "failed_feeds": 0,
        "checked": 1,
        "inserted": 0,
    }


def test_one_unavailable_feed_does_not_discard_healthy_official_news() -> None:
    bad = OfficialFeed(
        name="bad",
        url="https://www.bls.gov/feed/bad.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_bad",
        significance=80,
    )

    def transport(url: str, _headers: dict[str, str]) -> bytes:
        if url.endswith("bad.rss"):
            raise TimeoutError
        return rss()

    events, failures = OfficialRSSProvider((FEED, bad), transport).collect_events()

    assert len(events) == 1
    assert failures == {"bad": "TimeoutError"}
