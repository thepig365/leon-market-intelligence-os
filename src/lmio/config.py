"""Validated LMIO runtime configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with non-negotiable trading safety guards."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    environment: Literal["local", "test", "staging", "production"] = Field(
        default="local",
        validation_alias=AliasChoices("LMIO_ENVIRONMENT", "ENVIRONMENT"),
    )
    default_language: Literal["zh-CN"] = Field(
        default="zh-CN",
        validation_alias=AliasChoices("LMIO_DEFAULT_LANGUAGE", "DEFAULT_LANGUAGE"),
    )
    market: Literal["US_EQUITIES"] = Field(
        default="US_EQUITIES",
        validation_alias=AliasChoices("LMIO_MARKET", "MARKET"),
    )
    can_trade: bool = Field(default=False, validation_alias="CAN_TRADE")
    live_trading_enabled: bool = Field(
        default=False,
        validation_alias="LIVE_TRADING_ENABLED",
    )
    paper_trading_enabled: bool = Field(
        default=False,
        validation_alias="PAPER_TRADING_ENABLED",
    )
    database_path: Path = Field(
        default=Path("var/lmio.sqlite3"),
        validation_alias="LMIO_DATABASE_PATH",
    )
    sec_user_agent: str = Field(default="", validation_alias="SEC_USER_AGENT")
    telegram_bot_token: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", validation_alias="TELEGRAM_CHAT_ID")
    admin_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="LMIO_ADMIN_API_KEY")

    @model_validator(mode="after")
    def reject_trading_activation(self) -> Self:
        enabled = [
            name
            for name, value in (
                ("CAN_TRADE", self.can_trade),
                ("LIVE_TRADING_ENABLED", self.live_trading_enabled),
                ("PAPER_TRADING_ENABLED", self.paper_trading_enabled),
            )
            if value
        ]
        if enabled:
            joined = ", ".join(enabled)
            raise ValueError(f"LMIO V1 trading safety boundary violated: {joined} must be false")
        return self

    def public_health(self) -> dict[str, str | bool]:
        """Return the non-sensitive configuration suitable for health output."""

        return {
            "environment": self.environment,
            "default_language": self.default_language,
            "market": self.market,
            "can_trade": self.can_trade,
            "live_trading_enabled": self.live_trading_enabled,
            "paper_trading_enabled": self.paper_trading_enabled,
        }

    def integration_readiness(self) -> dict[str, bool]:
        return {
            "sec_configured": bool(self.sec_user_agent.strip()),
            "telegram_configured": bool(
                self.telegram_bot_token.strip() and self.telegram_chat_id.strip()
            ),
            "admin_api_key_configured": bool(self.admin_api_key.get_secret_value()),
        }


@lru_cache
def get_settings() -> Settings:
    """Load and cache validated settings."""

    return Settings()
