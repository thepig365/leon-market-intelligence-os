"""Signal outcome calculations for later strategy evaluation."""

from dataclasses import dataclass
from statistics import fmean, median

STANDARD_HORIZONS = {
    "1h": 0,
    "close": 1,
    "1d": 2,
    "5d": 6,
    "20d": 21,
}


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


def calculate_horizon_outcomes(
    signal_price: float,
    prices: list[float],
    *,
    strategy_horizon_index: int | None = None,
) -> dict[str, Outcome]:
    """Calculate only horizons supported by the supplied point-in-time series."""
    if not prices:
        raise ValueError("outcome prices are required")
    indexes = dict(STANDARD_HORIZONS)
    if strategy_horizon_index is not None:
        if strategy_horizon_index < 0:
            raise ValueError("strategy horizon index cannot be negative")
        indexes["strategy"] = strategy_horizon_index
    return {
        horizon: calculate_outcome(signal_price, prices[: index + 1])
        for horizon, index in indexes.items()
        if index < len(prices)
    }


@dataclass(frozen=True, slots=True)
class PerformanceSummary:
    sample_size: int
    hit_rate: float
    false_positive_rate: float
    average_return: float
    median_return: float
    average_max_drawdown: float
    average_excess_vs_spy: float | None
    average_excess_vs_sector: float | None


def summarise_performance(
    outcomes: list[Outcome],
    *,
    spy_returns: list[float] | None = None,
    sector_returns: list[float] | None = None,
) -> PerformanceSummary:
    if not outcomes:
        raise ValueError("at least one outcome is required")
    returns = [item.return_pct for item in outcomes]
    positives = sum(value > 0 for value in returns)
    if spy_returns is not None and len(spy_returns) != len(outcomes):
        raise ValueError("SPY benchmark count must match outcomes")
    if sector_returns is not None and len(sector_returns) != len(outcomes):
        raise ValueError("sector benchmark count must match outcomes")
    return PerformanceSummary(
        sample_size=len(outcomes),
        hit_rate=round(positives / len(outcomes), 6),
        false_positive_rate=round((len(outcomes) - positives) / len(outcomes), 6),
        average_return=round(fmean(returns), 6),
        median_return=round(median(returns), 6),
        average_max_drawdown=round(
            fmean(item.max_adverse_excursion_pct for item in outcomes),
            6,
        ),
        average_excess_vs_spy=(
            round(
                fmean(
                    value - benchmark for value, benchmark in zip(returns, spy_returns, strict=True)
                ),
                6,
            )
            if spy_returns is not None
            else None
        ),
        average_excess_vs_sector=(
            round(
                fmean(
                    value - benchmark
                    for value, benchmark in zip(returns, sector_returns, strict=True)
                ),
                6,
            )
            if sector_returns is not None
            else None
        ),
    )
