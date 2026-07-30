from datetime import UTC, datetime

from lmio.domain import SecuritySnapshot
from lmio.universe import UniversePolicy, build_investable_universe, exclusion_reasons


def snapshot(symbol: str, **updates: object) -> SecuritySnapshot:
    values = {
        "symbol": symbol,
        "company": symbol,
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "source": "test",
        "price": 10,
        "market_cap_m": 1000,
        "average_dollar_volume_m": 10,
    }
    values.update(updates)
    return SecuritySnapshot(**values)


def test_universe_is_filtered_deduplicated_and_sorted() -> None:
    items = [
        snapshot("bbb"),
        snapshot("AAA"),
        snapshot("AAA", observed_at=datetime(2026, 1, 2, tzinfo=UTC), price=12),
        snapshot("OTC", is_otc=True),
        snapshot("LOW", average_dollar_volume_m=1),
    ]

    result = build_investable_universe(items)

    assert [item.symbol for item in result] == ["AAA", "BBB"]
    assert result[0].price == 12


def test_exclusions_are_explicit() -> None:
    reasons = exclusion_reasons(
        snapshot("BAD", price=1, market_cap_m=10, average_dollar_volume_m=1),
        UniversePolicy(),
    )

    assert reasons == ["price", "market_cap", "liquidity"]
