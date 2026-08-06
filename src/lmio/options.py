"""Provider-neutral options observations and conservative unusual-volume research."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OptionRight(StrEnum):
    CALL = "call"
    PUT = "put"


class OptionDataMode(StrEnum):
    LIVE = "live"
    DELAYED = "delayed"
    MANUAL = "manual"


class OptionObservation(BaseModel):
    """One source-attributed contract snapshot; never an order instruction."""

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=10, pattern=r"^[A-Z][A-Z0-9.-]*$")
    expiry: date
    strike: float = Field(gt=0)
    right: OptionRight
    observed_at: datetime
    source: str = Field(min_length=1, max_length=80)
    source_url: str | None = Field(default=None, max_length=500)
    data_mode: OptionDataMode
    delay_minutes: int | None = Field(default=None, ge=0, le=120)
    underlying_price: float | None = Field(default=None, gt=0)
    bid: float | None = Field(default=None, ge=0)
    ask: float | None = Field(default=None, ge=0)
    last: float | None = Field(default=None, ge=0)
    volume: int | None = Field(default=None, ge=0)
    open_interest: int | None = Field(default=None, ge=0)
    implied_volatility: float | None = Field(default=None, ge=0, le=20)
    delta: float | None = Field(default=None, ge=-1, le=1)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_valid_market(self) -> OptionObservation:
        if self.bid is not None and self.ask is not None and self.ask < self.bid:
            raise ValueError("ask must be greater than or equal to bid")
        return self

    @property
    def contract_key(self) -> str:
        return f"{self.symbol}:{self.expiry.isoformat()}:{self.strike:g}:{self.right.value}"

    @property
    def fingerprint(self) -> str:
        material = f"{self.contract_key}:{self.source}:{self.observed_at.isoformat()}"
        return sha256(material.encode()).hexdigest()


class OptionBatch(BaseModel):
    """Bounded outbound-only batch accepted from an approved read-only bridge."""

    model_config = ConfigDict(extra="forbid")

    observed_at: datetime
    source: str = Field(pattern=r"^(ibkr_tws_paper_delayed|barchart_manual_csv)$")
    observations: list[OptionObservation] = Field(max_length=120)
    bridge_version: str = Field(default="2", pattern=r"^2$")

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_matching_source(self) -> OptionBatch:
        if any(item.source != self.source for item in self.observations):
            raise ValueError("every observation must use the batch source")
        return self


class OptionThresholds(BaseModel):
    min_volume: int = 500
    min_open_interest: int = 100
    min_volume_oi_ratio: float = 1.25
    min_price: float = 0.10
    max_spread_pct: float = 20.0
    min_dte: int = 7
    max_dte: int = 60


DEFAULT_THRESHOLDS = OptionThresholds()


def _csv_field(row: dict[str, str], *aliases: str) -> str:
    normalised = {
        str(key).strip().lower(): str(value or "").strip()
        for key, value in row.items()
        if key
    }
    return next(
        (normalised[name.lower()] for name in aliases if normalised.get(name.lower())),
        "",
    )


def _csv_number(value: str) -> float | None:
    cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
    if not cleaned or cleaned.upper() in {"-", "N/A", "NA"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _csv_expiry(value: str) -> date:
    for pattern in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported expiration date: {value}")


def parse_barchart_csv(
    csv_text: str,
    *,
    observed_at: datetime | None = None,
) -> OptionBatch:
    """Parse a user-downloaded CSV; no Barchart scraping or credential use."""

    timestamp = (observed_at or datetime.now(UTC)).astimezone(UTC)
    observations: list[OptionObservation] = []
    for row in csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"))):
        symbol = _csv_field(row, "Symbol", "Underlying").upper()
        option_type = _csv_field(row, "Type", "Put/Call", "Call/Put").lower()
        strike = _csv_number(_csv_field(row, "Strike", "Strike Price"))
        expiration = _csv_field(row, "Exp Date", "Expiration", "Expiration Date")
        if not symbol or strike is None or not expiration or option_type not in {"call", "put"}:
            continue
        iv = _csv_number(_csv_field(row, "IV", "Implied Volatility"))
        if iv is not None and iv > 3:
            iv /= 100
        observations.append(
            OptionObservation(
                symbol=symbol,
                expiry=_csv_expiry(expiration),
                strike=strike,
                right=option_type,
                observed_at=timestamp,
                source="barchart_manual_csv",
                source_url="https://www.barchart.com/options/unusual-activity",
                data_mode="manual",
                delay_minutes=30,
                underlying_price=_csv_number(_csv_field(row, "Price", "Underlying Price")),
                bid=_csv_number(_csv_field(row, "Bid")),
                ask=_csv_number(_csv_field(row, "Ask")),
                last=_csv_number(_csv_field(row, "Last", "Last Price")),
                volume=int(_csv_number(_csv_field(row, "Volume")) or 0),
                open_interest=int(
                    _csv_number(_csv_field(row, "Open Int", "Open Interest")) or 0
                ),
                implied_volatility=iv,
                delta=_csv_number(_csv_field(row, "Delta")),
            )
        )
        if len(observations) >= 120:
            break
    if not observations:
        raise ValueError("CSV did not contain any supported option rows")
    return OptionBatch(
        observed_at=timestamp,
        source="barchart_manual_csv",
        observations=observations,
    )


def _spread_pct(observation: OptionObservation) -> float | None:
    if observation.bid is None or observation.ask is None:
        return None
    midpoint = (observation.bid + observation.ask) / 2
    if midpoint <= 0:
        return None
    return round((observation.ask - observation.bid) / midpoint * 100, 2)


def classify_option(
    observation: OptionObservation,
    thresholds: OptionThresholds = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """Explain why a delayed contract is or is not an unusual-volume candidate."""

    dte = (observation.expiry - observation.observed_at.date()).days
    ratio = (
        observation.volume / observation.open_interest
        if observation.volume is not None and observation.open_interest
        else None
    )
    spread_pct = _spread_pct(observation)
    price = observation.last
    if price is None and observation.bid is not None and observation.ask is not None:
        price = (observation.bid + observation.ask) / 2

    missing = [
        label
        for label, value in (
            ("volume", observation.volume),
            ("open_interest", observation.open_interest),
            ("bid", observation.bid),
            ("ask", observation.ask),
        )
        if value is None
    ]
    checks = {
        "volume": observation.volume is not None
        and observation.volume >= thresholds.min_volume,
        "open_interest": observation.open_interest is not None
        and observation.open_interest >= thresholds.min_open_interest,
        "volume_oi_ratio": ratio is not None and ratio >= thresholds.min_volume_oi_ratio,
        "price": price is not None and price > thresholds.min_price,
        "spread": spread_pct is not None and spread_pct <= thresholds.max_spread_pct,
        "dte": thresholds.min_dte <= dte <= thresholds.max_dte,
    }
    reasons = [name for name, passed in checks.items() if passed]
    blocked = [name for name, passed in checks.items() if not passed]
    candidate = not missing and all(checks.values())

    indicative_sentiment = "direction_unverified"
    if observation.last is not None and observation.bid is not None and observation.ask is not None:
        if observation.last >= observation.ask:
            indicative_sentiment = (
                "bullish_indication"
                if observation.right is OptionRight.CALL
                else "bearish_indication"
            )
        elif observation.last <= observation.bid:
            indicative_sentiment = (
                "bearish_indication"
                if observation.right is OptionRight.CALL
                else "bullish_indication"
            )

    return {
        "contract_key": observation.contract_key,
        "candidate": candidate,
        "classification": "unusual_activity_candidate" if candidate else "not_qualified",
        "dte": dte,
        "volume_oi_ratio": round(ratio, 2) if ratio is not None else None,
        "spread_pct": spread_pct,
        "approximate_premium_usd": (
            round(price * observation.volume * 100, 2)
            if price is not None and observation.volume is not None
            else None
        ),
        "indicative_sentiment": indicative_sentiment,
        "missing_fields": missing,
        "passed_checks": reasons,
        "blocked_checks": blocked,
        "research_warning": (
            "异常成交量不能证明开仓、机构意图或未来方向；需结合次日未平仓量、"
            "公司事件和标的价格确认。"
        ),
        "thresholds": thresholds.model_dump(),
    }


def persisted_option(observation: OptionObservation) -> dict[str, Any]:
    return {
        **observation.model_dump(mode="json"),
        "analysis": classify_option(observation),
        "record_type": "options_research_only",
        "execution_allowed": False,
    }


def format_option_alert(payload: dict[str, Any]) -> str:
    """Create a bounded Chinese research alert without buy/sell language."""

    analysis = dict(payload.get("analysis") or {})
    right = "Call" if payload.get("right") == "call" else "Put"
    ratio = analysis.get("volume_oi_ratio")
    delay = payload.get("delay_minutes")
    return "\n".join(
        (
            "LMIO 期权研究提醒｜非交易信号",
            (
                f"{payload.get('symbol')} {payload.get('expiry')} "
                f"{payload.get('strike')} {right}"
            ),
            f"成交量：{payload.get('volume')}｜未平仓量：{payload.get('open_interest')}",
            f"成交量/OI：{ratio}｜价差：{analysis.get('spread_pct')}%",
            (
                f"行情：{payload.get('data_mode')}｜"
                f"延迟：{delay if delay is not None else '未知'} 分钟"
            ),
            "原因：成交量、未平仓量、比率、价格、价差和期限均达到研究门槛。",
            "下一步：核对公司事件、标的走势和下一交易日未平仓量变化。",
            "异常成交不代表机构方向；LMIO 不会据此下单。",
        )
    )
