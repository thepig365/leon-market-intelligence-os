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

    environment: Literal["local", "test", "preview", "production"] = Field(
        default="local",
        validation_alias=AliasChoices("LMIO_ENVIRONMENT", "ENVIRONMENT"),
    )
    allow_insecure_local_reads: bool = Field(
        default=False,
        validation_alias="LMIO_ALLOW_INSECURE_LOCAL_READS",
    )
    enable_demo_mode: bool = Field(default=False, validation_alias="LMIO_ENABLE_DEMO_MODE")
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
    store_backend: Literal["sqlite", "supabase"] = Field(
        default="sqlite",
        validation_alias="LMIO_STORE_BACKEND",
    )
    supabase_url: str = Field(default="", validation_alias="SUPABASE_URL")
    supabase_service_role_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="SUPABASE_SERVICE_ROLE_KEY",
    )
    read_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="LMIO_READ_API_KEY",
    )
    sec_user_agent: str = Field(default="", validation_alias="SEC_USER_AGENT")
    sec_watchlist: str = Field(
        default="AAPL:320193,META:1326801",
        validation_alias="LMIO_SEC_WATCHLIST",
    )
    telegram_bot_token: SecretStr = Field(
        default=SecretStr(""), validation_alias="TELEGRAM_BOT_TOKEN"
    )
    telegram_chat_id: SecretStr = Field(default=SecretStr(""), validation_alias="TELEGRAM_CHAT_ID")
    telegram_webhook_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="TELEGRAM_WEBHOOK_SECRET",
    )
    public_base_url: str = Field(default="", validation_alias="LMIO_PUBLIC_BASE_URL")
    finviz_api_token: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="FINVIZ_API_TOKEN",
    )
    cron_secret: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="CRON_SECRET",
    )
    openai_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="OPENAI_API_KEY",
    )
    openai_model: str = Field(default="", validation_alias="LMIO_OPENAI_MODEL")
    admin_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="LMIO_ADMIN_API_KEY")
    owner_identity: str = Field(default="leon", validation_alias="LMIO_OWNER_IDENTITY")
    release_sha: str = Field(default="unrecorded", validation_alias="LMIO_RELEASE_SHA")
    vercel_git_commit_sha: str = Field(default="", validation_alias="VERCEL_GIT_COMMIT_SHA")
    release_label: str = Field(
        default="LMIO v1.0 RC1 — Ready for Operator Acceptance",
        validation_alias="LMIO_RELEASE_LABEL",
    )

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
        if self.store_backend == "supabase":
            if not self.supabase_url.strip():
                raise ValueError("SUPABASE_URL is required when LMIO_STORE_BACKEND=supabase")
            if not self.supabase_service_role_key.get_secret_value():
                raise ValueError(
                    "SUPABASE_SERVICE_ROLE_KEY is required when LMIO_STORE_BACKEND=supabase"
                )
            if not self.read_api_key.get_secret_value():
                raise ValueError("LMIO_READ_API_KEY is required for a Supabase-backed runtime")
        return self

    def public_health(self) -> dict[str, str | bool]:
        """Return the non-sensitive configuration suitable for health output."""

        return {
            "environment": self.environment,
            "insecure_local_reads_enabled": (
                self.environment == "local" and self.allow_insecure_local_reads
            ),
            "demo_mode_enabled": self.enable_demo_mode,
            "default_language": self.default_language,
            "market": self.market,
            "can_trade": self.can_trade,
            "live_trading_enabled": self.live_trading_enabled,
            "paper_trading_enabled": self.paper_trading_enabled,
            "store_backend": self.store_backend,
            "release_sha": self.resolved_release_sha,
            "release_label": self.release_label,
        }

    @property
    def resolved_release_sha(self) -> str:
        """Prefer an explicit release SHA, then Vercel's immutable deployment SHA."""

        if self.release_sha.strip() and self.release_sha != "unrecorded":
            return self.release_sha.strip()
        return self.vercel_git_commit_sha.strip() or "unrecorded"

    def integration_readiness(self) -> dict[str, bool]:
        return {
            "sec_configured": bool(self.sec_user_agent.strip()),
            "telegram_configured": bool(
                self.telegram_bot_token.get_secret_value().strip()
                and self.telegram_chat_id.get_secret_value().strip()
            ),
            "telegram_queries_configured": bool(
                self.telegram_bot_token.get_secret_value().strip()
                and self.telegram_chat_id.get_secret_value().strip()
                and self.telegram_webhook_secret.get_secret_value()
            ),
            "finviz_configured": bool(self.finviz_api_token.get_secret_value()),
            "scheduled_refresh_configured": bool(self.cron_secret.get_secret_value()),
            "openai_research_configured": bool(
                self.openai_api_key.get_secret_value() and self.openai_model.strip()
            ),
            "admin_api_key_configured": bool(self.admin_api_key.get_secret_value()),
            "read_api_key_configured": bool(self.read_api_key.get_secret_value()),
        }

    def parsed_sec_watchlist(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for pair in self.sec_watchlist.split(","):
            if not pair.strip():
                continue
            try:
                symbol, cik = pair.split(":", maxsplit=1)
            except ValueError as error:
                raise ValueError("LMIO_SEC_WATCHLIST must use SYMBOL:CIK pairs") from error
            symbol = symbol.strip().upper()
            cik = cik.strip().lstrip("0")
            if not symbol or not cik.isdigit():
                raise ValueError("LMIO_SEC_WATCHLIST contains an invalid SYMBOL:CIK pair")
            result[symbol] = cik
        return result


@lru_cache
def get_settings() -> Settings:
    """Load and cache validated settings."""

    return Settings()
