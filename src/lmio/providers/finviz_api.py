"""Server-side Finviz Elite API adapter for authorised internal research."""

import csv
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import StringIO
from time import sleep

import httpx

from lmio.domain import DataProvenance, MarketEnvironmentSnapshot, SecuritySnapshot
from lmio.providers.base import ProviderHealth, ProviderState
from lmio.providers.contracts import MarketDataProvider
from lmio.providers.csv_snapshot import MAX_CSV_BYTES
from lmio.providers.finviz_csv import FinvizCSVProvider

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"
FINVIZ_COLUMNS = (
    "1,2,3,4,5,129,6,8,22,23,39,40,34,38,45,54,127,64,63,67,65,66,59,29,30,31"
)
VIX_HISTORY_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
FinvizTransport = Callable[[str, dict[str, str], float], httpx.Response]
VixTransport = Callable[[str, float], httpx.Response]


def _default_transport(
    url: str,
    params: dict[str, str],
    timeout: float,
) -> httpx.Response:
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "LMIO/1.0 authorised internal research"},
    ) as client:
        return client.get(url, params=params)


def _default_vix_transport(url: str, timeout: float) -> httpx.Response:
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "LMIO/1.0 internal market-environment research"},
    ) as client:
        return client.get(url)


def _percentage(value: str | None) -> float | None:
    if value is None:
        return None
    normalised = value.strip().replace(",", "")
    if not normalised or normalised == "-":
        return None
    if normalised.endswith("%"):
        normalised = normalised[:-1]
    return float(normalised)


class FinvizAPIProvider(MarketDataProvider):
    """Fetch and normalise one bounded Finviz Elite screener snapshot."""

    name = "finviz_elite_api"

    def __init__(
        self,
        api_token: str,
        *,
        transport: FinvizTransport | None = None,
        vix_transport: VixTransport | None = None,
        wait: Callable[[float], None] = sleep,
    ) -> None:
        self._api_token = api_token.strip()
        self._transport = transport or _default_transport
        self._vix_transport = vix_transport or _default_vix_transport
        self._wait = wait
        self._health = ProviderHealth(
            provider=self.name,
            state=(
                ProviderState.CONFIGURED_NOT_VERIFIED if self._api_token else ProviderState.DISABLED
            ),
            detail=(
                "awaiting first authorised Finviz API refresh"
                if self._api_token
                else "Finviz API token is not configured"
            ),
        )
        self._last_ingestion_evidence: dict[str, object] | None = None
        self._benchmark_changes: dict[str, float] = {}

    @property
    def last_ingestion_evidence(self) -> dict[str, object] | None:
        return self._last_ingestion_evidence

    def health(self) -> ProviderHealth:
        return self._health

    def snapshots(self, symbols: list[str] | None = None) -> list[SecuritySnapshot]:
        if not self._api_token:
            raise RuntimeError("Finviz API is not configured")

        retrieval_started = datetime.now(UTC)

        requested_symbols = sorted(
            {symbol.strip().upper() for symbol in (symbols or []) if symbol.strip()}
        )
        response: httpx.Response | None = None
        for attempt in range(3):
            params = {
                "v": "152",
                "c": FINVIZ_COLUMNS,
                "auth": self._api_token,
            }
            if requested_symbols:
                params["t"] = ",".join(requested_symbols)
            response = self._transport(
                FINVIZ_EXPORT_URL,
                params,
                30.0,
            )
            if response.status_code != 429:
                break
            if attempt < 2:
                self._wait(float(2**attempt * 5))

        assert response is not None
        response.raise_for_status()
        raw = response.content
        if len(raw) > MAX_CSV_BYTES:
            raise ValueError("Finviz API response exceeds the configured size limit")
        content_type = response.headers.get("content-type", "").lower()
        if content_type and not any(
            allowed in content_type
            for allowed in ("text/csv", "text/plain", "application/octet-stream")
        ):
            raise ValueError("Finviz API returned an unexpected content type")

        checksum = sha256(raw).hexdigest()
        decoded = raw.decode("utf-8-sig")
        rows = list(csv.DictReader(StringIO(decoded)))
        self._benchmark_changes = {
            ticker: change
            for row in rows
            if (ticker := str(row.get("Ticker", "")).strip().upper()) in {"SPY", "QQQ", "IWM"}
            and (change := _percentage(row.get("Change"))) is not None
        }
        parser = FinvizCSVProvider()
        observed_at = datetime.now(UTC)
        snapshots = parser.parse(
            decoded,
            observed_at=observed_at,
            provenance=DataProvenance.LIVE_AUTHORISED,
        )
        completed_at = datetime.now(UTC)
        counts = parser.parse_counts
        self._last_ingestion_evidence = {
            "provider": self.name,
            "endpoint": FINVIZ_EXPORT_URL,
            "endpoint_version": "v=152",
            "retrieval_started_at": retrieval_started.isoformat(),
            "retrieval_completed_at": completed_at.isoformat(),
            "market_timestamp": observed_at.isoformat(),
            "market_timestamp_basis": "retrieval_time_no_provider_timestamp",
            "timezone": "UTC",
            "http_status": response.status_code,
            "row_count_received": counts["accepted"] + counts["rejected"],
            "row_count_accepted": counts["accepted"],
            "row_count_rejected": counts["rejected"],
            "duplicate_count": counts["duplicates"],
            "missing_required_fields": [],
            "stale_status": "fresh_at_retrieval",
            "checksum_sha256": checksum,
            "snapshot_id": f"finviz:{checksum[:24]}",
        }
        self._health = ProviderHealth(
            provider=self.name,
            state=ProviderState.READY,
            detail=(
                f"authorised Finviz API refresh accepted {len(snapshots)} equities"
                if not requested_symbols
                else (
                    "authorised Finviz API lookup accepted "
                    f"{len(snapshots)} of {len(requested_symbols)} requested symbols"
                )
            ),
        )
        return snapshots

    def market_environment(
        self,
        snapshots: list[SecuritySnapshot],
        *,
        now: datetime | None = None,
    ) -> MarketEnvironmentSnapshot:
        """Build one verified benchmark snapshot from licensed Finviz and official Cboe data."""

        missing = {"SPY", "QQQ", "IWM"} - self._benchmark_changes.keys()
        if missing:
            raise ValueError(
                "Finviz market snapshot is missing benchmark changes: "
                + ", ".join(sorted(missing))
            )
        breadth_values = [
            item.daily_change_pct for item in snapshots if item.daily_change_pct is not None
        ]
        if len(breadth_values) < 100:
            raise ValueError("Finviz market breadth coverage is insufficient")

        response = self._vix_transport(VIX_HISTORY_URL, 30.0)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if content_type and not any(
            allowed in content_type
            for allowed in ("text/csv", "text/plain", "application/octet-stream")
        ):
            raise ValueError("Cboe VIX history returned an unexpected content type")
        vix_rows = list(csv.DictReader(StringIO(response.text.lstrip("\ufeff"))))
        if not vix_rows:
            raise ValueError("Cboe VIX history returned no observations")
        latest = vix_rows[-1]
        vix = _percentage(latest.get("CLOSE"))
        date_text = str(latest.get("DATE", "")).strip()
        if vix is None or not date_text:
            raise ValueError("Cboe VIX history is missing its latest close")
        observed_date = datetime.strptime(date_text, "%m/%d/%Y").replace(tzinfo=UTC)
        checked_at = (now or datetime.now(UTC)).astimezone(UTC)
        if checked_at - observed_date > timedelta(days=5):
            raise ValueError("Cboe VIX close is stale")

        return MarketEnvironmentSnapshot(
            observed_at=checked_at,
            spy_return_pct=self._benchmark_changes["SPY"],
            qqq_return_pct=self._benchmark_changes["QQQ"],
            iwm_return_pct=self._benchmark_changes["IWM"],
            vix=vix,
            breadth_pct=sum(value > 0 for value in breadth_values) / len(breadth_values) * 100,
            breadth_observations=len(breadth_values),
            vix_observed_on=observed_date.date().isoformat(),
            source_urls=[FINVIZ_EXPORT_URL, VIX_HISTORY_URL],
        )
