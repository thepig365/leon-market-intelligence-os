"""Signal outcome calculations for later strategy evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Outcome:
    return_pct: float
    max_adverse_excursion_pct: float
    max_favourable_excursion_pct: float


def calculate_outcome(signal_price: float, closes: list[float]) -> Outcome:
    if signal_price <= 0:
        raise ValueError("signal_price must be positive")
    if not closes or any(price <= 0 for price in closes):
        raise ValueError("positive outcome prices are required")
    returns = [(price - signal_price) / signal_price for price in closes]
    return Outcome(
        return_pct=round(returns[-1], 6),
        max_adverse_excursion_pct=round(min(returns), 6),
        max_favourable_excursion_pct=round(max(returns), 6),
    )
