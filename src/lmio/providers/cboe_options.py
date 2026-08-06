"""Free, no-login Cboe most-active options research feed."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

CBOE_MOST_ACTIVE_ENDPOINT = (
    "https://www-api.cboe.com/us/options/market_statistics/most_active/data/"
)
CBOE_MOST_ACTIVE_PAGE = (
    "https://www.cboe.com/markets/us/options/market-statistics/most-active/"
)
CBOE_RESPONSE_LIMIT_BYTES = 1_000_000
CboeTransport = Callable[[str, dict[str, str], float], httpx.Response]


def _default_transport(
    url: str,
    params: dict[str, str],
    timeout: float,
) -> httpx.Response:
    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "LMIO/1.0 internal options-volume research"},
    ) as client:
        return client.get(url, params=params)


class CboeActiveContract(BaseModel):
    """One public Cboe leaderboard row, not an unusual-activity signal."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=20)
    expiry: date
    strike: float = Field(gt=0)
    right: Literal["call", "put"]
    volume: int = Field(ge=0)

    @field_validator("symbol")
    @classmethod
    def normalise_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol or any(character.isspace() for character in symbol):
            raise ValueError("symbol must be a non-empty market identifier")
        return symbol


class CboeMostActiveSnapshot(BaseModel):
    """Bounded equity-options leaderboard with explicit provenance."""

    model_config = ConfigDict(extra="forbid")

    market_timestamp: datetime
    retrieved_at: datetime
    calls: list[CboeActiveContract] = Field(max_length=25)
    puts: list[CboeActiveContract] = Field(max_length=25)

    @field_validator("market_timestamp", "retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(UTC)

    @property
    def total_contracts(self) -> int:
        return len(self.calls) + len(self.puts)

    def high_volume_tickers(self) -> list[dict[str, object]]:
        """Aggregate only volumes visible in the bounded Cboe leaderboard."""

        totals: dict[str, dict[str, int | str]] = {}
        for contract in [*self.calls, *self.puts]:
            ticker = totals.setdefault(
                contract.symbol,
                {
                    "symbol": contract.symbol,
                    "leaderboard_volume": 0,
                    "call_volume": 0,
                    "put_volume": 0,
                    "contract_count": 0,
                },
            )
            ticker["leaderboard_volume"] = int(ticker["leaderboard_volume"]) + contract.volume
            key = "call_volume" if contract.right == "call" else "put_volume"
            ticker[key] = int(ticker[key]) + contract.volume
            ticker["contract_count"] = int(ticker["contract_count"]) + 1
        return sorted(
            totals.values(),
            key=lambda item: int(item["leaderboard_volume"]),
            reverse=True,
        )


def _number(value: object, *, integer: bool = False) -> float | int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a market number")
    cleaned = str(value).replace(",", "").strip()
    number = float(cleaned)
    return int(number) if integer else number


def _contracts(rows: object, right: Literal["call", "put"]) -> list[CboeActiveContract]:
    if not isinstance(rows, list):
        raise ValueError(f"Cboe {right} rows are not a list")
    contracts: list[CboeActiveContract] = []
    for row in rows[:25]:
        if not isinstance(row, dict):
            raise ValueError(f"Cboe {right} row is not an object")
        contracts.append(
            CboeActiveContract(
                symbol=str(row.get("symbol", "")),
                expiry=str(row.get("expires", "")),
                strike=_number(row.get("strike")),
                right=right,
                volume=_number(row.get("volume"), integer=True),
            )
        )
    return contracts


def parse_cboe_most_active(
    payload: object,
    *,
    retrieved_at: datetime | None = None,
) -> CboeMostActiveSnapshot:
    """Parse only Cboe's equity-options category and reject schema drift."""

    if not isinstance(payload, dict) or not isinstance(payload.get("categories"), list):
        raise ValueError("Cboe response is missing categories")
    category = next(
        (
            item
            for item in payload["categories"]
            if isinstance(item, dict) and item.get("category") == "equity"
        ),
        None,
    )
    if category is None:
        raise ValueError("Cboe response is missing the equity-options category")
    timestamp = datetime.fromisoformat(str(payload.get("dt", "")).replace("Z", "+00:00"))
    return CboeMostActiveSnapshot(
        market_timestamp=timestamp,
        retrieved_at=(retrieved_at or datetime.now(UTC)).astimezone(UTC),
        calls=_contracts(category.get("calls"), "call"),
        puts=_contracts(category.get("puts"), "put"),
    )


class CboeMostActiveProvider:
    """Fetch Cboe's public, delayed most-active equity-options leaderboard."""

    name = "cboe_options_most_active"

    def __init__(self, *, transport: CboeTransport | None = None) -> None:
        self._transport = transport or _default_transport

    def snapshot(self, *, limit: int = 25) -> CboeMostActiveSnapshot:
        bounded_limit = max(1, min(limit, 25))
        response = self._transport(
            CBOE_MOST_ACTIVE_ENDPOINT,
            {"mkt": "cone", "limit": str(bounded_limit)},
            20.0,
        )
        response.raise_for_status()
        if len(response.content) > CBOE_RESPONSE_LIMIT_BYTES:
            raise ValueError("Cboe response exceeds the configured size limit")
        content_type = response.headers.get("content-type", "").lower()
        if content_type and "json" not in content_type:
            raise ValueError("Cboe returned an unexpected content type")
        return parse_cboe_most_active(response.json())


def snapshot_payload(snapshot: CboeMostActiveSnapshot) -> dict[str, Any]:
    return {
        "detail": (
            "delayed Cboe equity-options leaderboard available"
            if snapshot.total_contracts
            else "Cboe returned no current-session equity-options rows"
        ),
        "source": "Cboe Options Exchange",
        "source_url": CBOE_MOST_ACTIVE_PAGE,
        "endpoint": CBOE_MOST_ACTIVE_ENDPOINT,
        "market_timestamp": snapshot.market_timestamp.isoformat(),
        "retrieved_at": snapshot.retrieved_at.isoformat(),
        "data_mode": "delayed_at_least_20_minutes",
        "exchange_scope": "Cboe Options Exchange only; not consolidated US options volume",
        "category": "equity_options",
        "total_contracts": snapshot.total_contracts,
        "calls": [item.model_dump(mode="json") for item in snapshot.calls],
        "puts": [item.model_dump(mode="json") for item in snapshot.puts],
        "high_volume_tickers": snapshot.high_volume_tickers(),
        "execution_allowed": False,
    }
