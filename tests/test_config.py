import pytest
from pydantic import ValidationError

from lmio.config import Settings


def test_safe_defaults_are_locked() -> None:
    settings = Settings(_env_file=None)

    assert settings.default_language == "zh-CN"
    assert settings.market == "US_EQUITIES"
    assert settings.can_trade is False
    assert settings.live_trading_enabled is False
    assert settings.paper_trading_enabled is False
    assert settings.parsed_sec_watchlist() == {
        "AAPL": "320193",
        "META": "1326801",
    }


@pytest.mark.parametrize(
    "field",
    ["can_trade", "live_trading_enabled", "paper_trading_enabled"],
)
def test_trading_activation_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match="trading safety boundary violated"):
        Settings(_env_file=None, **{field: True})
