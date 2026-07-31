"""Read-only adapters for high-value United States government RSS releases."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib import request
from urllib.parse import urlsplit
from xml.etree import ElementTree

from lmio.domain import NewsEvent
from lmio.providers.base import Provider, ProviderHealth, ProviderState

MAX_FEED_BYTES = 2 * 1024 * 1024
OFFICIAL_NEWS_HOSTS = {"www.bls.gov", "www.federalreserve.gov"}
Transport = Callable[[str, dict[str, str]], bytes]


@dataclass(frozen=True, slots=True)
class OfficialFeed:
    name: str
    url: str
    source: str
    event_type: str
    significance: float


DEFAULT_OFFICIAL_FEEDS = (
    OfficialFeed(
        name="federal_reserve_monetary_policy",
        url="https://www.federalreserve.gov/feeds/press_monetary.xml",
        source="Federal Reserve",
        event_type="macro_monetary_policy",
        significance=95,
    ),
    OfficialFeed(
        name="bls_employment_situation",
        url="https://www.bls.gov/feed/empsit.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_employment",
        significance=92,
    ),
    OfficialFeed(
        name="bls_consumer_price_index",
        url="https://www.bls.gov/feed/cpi.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_inflation_cpi",
        significance=92,
    ),
    OfficialFeed(
        name="bls_producer_price_index",
        url="https://www.bls.gov/feed/ppi.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_inflation_ppi",
        significance=85,
    ),
    OfficialFeed(
        name="bls_job_openings",
        url="https://www.bls.gov/feed/jolts.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_job_openings",
        significance=82,
    ),
)


def _urlopen_transport(url: str, headers: dict[str, str]) -> bytes:
    with request.urlopen(request.Request(url, headers=headers), timeout=15) as response:
        return response.read(MAX_FEED_BYTES + 1)


def _safe_official_url(url: str) -> bool:
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname in OFFICIAL_NEWS_HOSTS


def _text(element: ElementTree.Element, names: Iterable[str]) -> str:
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _published_at(value: str) -> datetime:
    if not value:
        raise ValueError("official feed item is missing its publication time")
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class OfficialRSSProvider(Provider):
    """Fetch a bounded, allowlisted set of official macroeconomic releases."""

    name = "official_macro_news"

    def __init__(
        self,
        feeds: tuple[OfficialFeed, ...] = DEFAULT_OFFICIAL_FEEDS,
        transport: Transport | None = None,
    ) -> None:
        self.feeds = feeds
        self.transport = transport or _urlopen_transport

    def health(self) -> ProviderHealth:
        if not self.feeds:
            return ProviderHealth(self.name, ProviderState.DISABLED, "no official feeds configured")
        try:
            self._fetch(self.feeds[0])
        except Exception as error:
            return ProviderHealth(self.name, ProviderState.UNAVAILABLE, type(error).__name__)
        return ProviderHealth(self.name, ProviderState.READY)

    def events(self) -> list[NewsEvent]:
        events, failures = self.collect_events()
        if failures and len(failures) == len(self.feeds):
            raise RuntimeError("all official feeds were unavailable")
        return events

    def collect_events(self) -> tuple[list[NewsEvent], dict[str, str]]:
        """Keep healthy feeds useful when one official endpoint is temporarily down."""

        events: list[NewsEvent] = []
        failures: dict[str, str] = {}
        for feed in self.feeds:
            try:
                events.extend(self._fetch(feed))
            except Exception as error:
                failures[feed.name] = type(error).__name__
        return events, failures

    def _fetch(self, feed: OfficialFeed) -> list[NewsEvent]:
        if not _safe_official_url(feed.url):
            raise ValueError("official feed URL is not allowlisted")
        raw = self.transport(
            feed.url,
            {"User-Agent": "LMIO read-only research/1.0", "Accept": "application/rss+xml"},
        )
        if len(raw) > MAX_FEED_BYTES:
            raise ValueError("official feed exceeds the configured size limit")
        root = ElementTree.fromstring(raw)
        items = root.findall("./channel/item")
        if not items:
            items = root.findall("{http://www.w3.org/2005/Atom}entry")
        events: list[NewsEvent] = []
        for item in items:
            headline = _text(
                item,
                ("title", "{http://www.w3.org/2005/Atom}title"),
            )
            source_url = _text(item, ("link",))
            if not source_url:
                atom_link = item.find("{http://www.w3.org/2005/Atom}link")
                source_url = atom_link.get("href", "") if atom_link is not None else ""
            published = _text(
                item,
                (
                    "pubDate",
                    "{http://purl.org/dc/elements/1.1/}date",
                    "{http://www.w3.org/2005/Atom}updated",
                    "{http://www.w3.org/2005/Atom}published",
                ),
            )
            if not headline or not _safe_official_url(source_url):
                continue
            events.append(
                NewsEvent(
                    headline=headline,
                    source=feed.source,
                    source_url=source_url,
                    source_tier=1,
                    published_at=_published_at(published),
                    symbols=[],
                    event_type=feed.event_type,
                    significance=feed.significance,
                    surprise=0,
                    confidence=1,
                )
            )
        return events
