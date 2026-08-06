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
    assert settings.allow_insecure_local_reads is False
    assert settings.finviz_api_token.get_secret_value() == ""
    assert settings.cron_secret.get_secret_value() == ""
    assert settings.ibkr_bridge_key.get_secret_value() == ""
    assert settings.integration_readiness()["ibkr_bridge_configured"] is False
    assert settings.parsed_sec_watchlist() == {
        "AAPL": "320193",
        "META": "1326801",
    }


def test_vercel_commit_sha_is_used_when_release_sha_is_not_explicit() -> None:
    settings = Settings(_env_file=None, vercel_git_commit_sha="deployment-sha")

    assert settings.resolved_release_sha == "deployment-sha"
    assert settings.public_health()["release_sha"] == "deployment-sha"


def test_explicit_release_sha_takes_precedence_over_vercel_sha() -> None:
    settings = Settings(
        _env_file=None,
        release_sha="approved-release-sha",
        vercel_git_commit_sha="deployment-sha",
    )

    assert settings.resolved_release_sha == "approved-release-sha"


@pytest.mark.parametrize(
    "field",
    ["can_trade", "live_trading_enabled", "paper_trading_enabled"],
)
def test_trading_activation_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError, match="trading safety boundary violated"):
        Settings(_env_file=None, **{field: True})


def test_unknown_runtime_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="unknown")
