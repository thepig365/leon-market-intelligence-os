"""Read-only adapters for high-value United States government RSS releases."""

import json
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
BLSTransport = Callable[[str, dict[str, str], bytes], bytes]
BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


@dataclass(frozen=True, slots=True)
class OfficialFeed:
    name: str
    url: str
    source: str
    event_type: str
    significance: float
    fallback_series_id: str | None = None
    fallback_label: str | None = None
    fallback_unit: str | None = None
    fallback_url: str | None = None


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
        fallback_series_id="CEU0000000001",
        fallback_label="BLS total nonfarm employment",
        fallback_unit="thousand jobs",
        fallback_url="https://www.bls.gov/ces/",
    ),
    OfficialFeed(
        name="bls_consumer_price_index",
        url="https://www.bls.gov/feed/cpi.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_inflation_cpi",
        significance=92,
        fallback_series_id="CUUR0000SA0",
        fallback_label="BLS CPI all items",
        fallback_unit="index points",
        fallback_url="https://www.bls.gov/cpi/",
    ),
    OfficialFeed(
        name="bls_producer_price_index",
        url="https://www.bls.gov/feed/ppi.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_inflation_ppi",
        significance=85,
        fallback_series_id="WPUFD4",
        fallback_label="BLS PPI final demand",
        fallback_unit="index points",
        fallback_url="https://www.bls.gov/ppi/",
    ),
    OfficialFeed(
        name="bls_job_openings",
        url="https://www.bls.gov/feed/jolts.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_job_openings",
        significance=82,
        fallback_series_id="JTS000000000000000JOL",
        fallback_label="BLS total nonfarm job openings",
        fallback_unit="thousand openings",
        fallback_url="https://www.bls.gov/jlt/",
    ),
)


def _urlopen_transport(url: str, headers: dict[str, str]) -> bytes:
    with request.urlopen(request.Request(url, headers=headers), timeout=15) as response:
        return response.read(MAX_FEED_BYTES + 1)


def _bls_api_transport(url: str, headers: dict[str, str], body: bytes) -> bytes:
    request_object = request.Request(url, data=body, headers=headers, method="POST")
    with request.urlopen(request_object, timeout=15) as response:
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
        bls_transport: BLSTransport | None = None,
    ) -> None:
        self.feeds = feeds
        self.transport = transport or _urlopen_transport
        self.bls_transport = bls_transport or _bls_api_transport

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
                if feed.fallback_series_id:
                    try:
                        events.extend(self._fetch_bls_series(feed))
                    except Exception as fallback_error:
                        failures[feed.name] = type(fallback_error).__name__
                else:
                    failures[feed.name] = type(error).__name__
        return events, failures

    def _fetch_bls_series(self, feed: OfficialFeed) -> list[NewsEvent]:
        """Use BLS's free public API when its RSS endpoints reject server traffic."""

        if not feed.fallback_series_id or not feed.fallback_url:
            raise ValueError("BLS fallback is not configured")
        now = datetime.now(UTC)
        body = json.dumps(
            {
                "seriesid": [feed.fallback_series_id],
                "startyear": str(now.year - 1),
                "endyear": str(now.year),
            }
        ).encode()
        raw = self.bls_transport(
            BLS_API_URL,
            {
                "User-Agent": "LMIO read-only research/1.0",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            body,
        )
        if len(raw) > MAX_FEED_BYTES:
            raise ValueError("BLS API response exceeds the configured size limit")
        payload = json.loads(raw)
        if payload.get("status") != "REQUEST_SUCCEEDED":
            raise ValueError("BLS API request did not succeed")
        series = list(payload.get("Results", {}).get("series", []))
        if not series or series[0].get("seriesID") != feed.fallback_series_id:
            raise ValueError("BLS API response did not contain the requested series")
        observations = [
            item
            for item in list(series[0].get("data", []))
            if str(item.get("period", "")).startswith("M") and str(item.get("value", "")).strip()
        ]
        if not observations:
            raise ValueError("BLS API response contained no monthly observations")
        latest = observations[0]
        previous = observations[1] if len(observations) > 1 else None
        label = feed.fallback_label or feed.name
        unit = feed.fallback_unit or ""
        headline = (
            f"{label}: {latest['value']} {unit} for "
            f"{latest.get('periodName', latest['period'])} {latest['year']}"
        ).strip()
        if previous:
            headline += f"; previous {previous['value']} {unit}"
        return [
            NewsEvent(
                headline=headline,
                source=feed.source,
                source_url=feed.fallback_url,
                source_tier=1,
                published_at=now,
                symbols=[],
                event_type=feed.event_type,
                significance=feed.significance,
                surprise=0,
                confidence=1,
            )
        ]

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
