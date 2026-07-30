"""Reproducible United States equity universe construction."""

from dataclasses import dataclass

from lmio.domain import SecuritySnapshot


@dataclass(frozen=True, slots=True)
class UniversePolicy:
    min_price: float = 3
    min_market_cap_m: float = 300
    min_average_dollar_volume_m: float = 5
    allowed_exchanges: tuple[str, ...] = ("NYSE", "NASDAQ", "AMEX")
    version: str = "universe-v1"


def exclusion_reasons(item: SecuritySnapshot, policy: UniversePolicy) -> list[str]:
    reasons: list[str] = []
    if not item.is_common_stock:
        reasons.append("not_common_stock")
    if item.is_otc:
        reasons.append("otc")
    if item.exchange not in policy.allowed_exchanges:
        reasons.append("exchange")
    if item.price < policy.min_price:
        reasons.append("price")
    if item.market_cap_m < policy.min_market_cap_m:
        reasons.append("market_cap")
    if item.average_dollar_volume_m < policy.min_average_dollar_volume_m:
        reasons.append("liquidity")
    return reasons


def build_investable_universe(
    snapshots: list[SecuritySnapshot], policy: UniversePolicy | None = None
) -> list[SecuritySnapshot]:
    """Return a stable symbol-sorted universe from immutable snapshots."""

    active_policy = policy or UniversePolicy()
    by_symbol: dict[str, SecuritySnapshot] = {}
    for item in snapshots:
        symbol = item.symbol.strip().upper()
        normalised = item.model_copy(update={"symbol": symbol})
        if not exclusion_reasons(normalised, active_policy):
            existing = by_symbol.get(symbol)
            if existing is None or normalised.observed_at > existing.observed_at:
                by_symbol[symbol] = normalised
    return [by_symbol[symbol] for symbol in sorted(by_symbol)]
