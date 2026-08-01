"""Server-side Finviz Elite API adapter for authorised internal research."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from time import sleep

import httpx

from lmio.domain import DataProvenance, SecuritySnapshot
from lmio.providers.base import ProviderHealth, ProviderState
from lmio.providers.contracts import MarketDataProvider
from lmio.providers.csv_snapshot import MAX_CSV_BYTES
from lmio.providers.finviz_csv import FinvizCSVProvider

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"
FINVIZ_COLUMNS = "1,2,3,4,5,129,6,8,22,23,39,40,34,38,45,54,127,64,63,67,65,59,29,30,31"
FinvizTransport = Callable[[str, dict[str, str], float], httpx.Response]


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


class FinvizAPIProvider(MarketDataProvider):
    """Fetch and normalise one bounded Finviz Elite screener snapshot."""

    name = "finviz_elite_api"

    def __init__(
        self,
        api_token: str,
        *,
        transport: FinvizTransport | None = None,
        wait: Callable[[float], None] = sleep,
    ) -> None:
        self._api_token = api_token.strip()
        self._transport = transport or _default_transport
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

    def health(self) -> ProviderHealth:
        return self._health

    def snapshots(self, symbols: list[str] | None = None) -> list[SecuritySnapshot]:
        if not self._api_token:
            raise RuntimeError("Finviz API is not configured")

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

        parser = FinvizCSVProvider()
        snapshots = parser.parse(
            raw.decode("utf-8-sig"),
            observed_at=datetime.now(UTC),
            provenance=DataProvenance.LIVE_AUTHORISED,
        )
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
