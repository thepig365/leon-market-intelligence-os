"""Strict, minimal-data contract for the outbound-only local IBKR bridge."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IBKRNewsProviderInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=24, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=1, max_length=120)


class IBKRBridgeHeartbeat(BaseModel):
    """No account identifiers, balances, positions, orders, or news content."""

    model_config = ConfigDict(extra="forbid")

    observed_at: datetime
    connected: bool
    paper_account_confirmed: bool
    paper_order_permission_confirmed: bool
    news_providers: list[IBKRNewsProviderInfo] = Field(default_factory=list, max_length=12)
    headline_probe_count: int = Field(default=0, ge=0, le=100)
    bridge_version: str = Field(default="1", pattern=r"^1$")

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value

    def provider_state(self) -> str:
        if not self.connected:
            return "unavailable"
        if not self.paper_account_confirmed or not self.news_providers:
            return "degraded"
        return "ready"

    def safe_payload(self) -> dict[str, object]:
        return {
            "observed_at": self.observed_at.isoformat(),
            "connected": self.connected,
            "paper_account_confirmed": self.paper_account_confirmed,
            "paper_order_permission_confirmed": self.paper_order_permission_confirmed,
            "news_providers": [item.model_dump() for item in self.news_providers],
            "headline_probe_count": self.headline_probe_count,
            "bridge_version": self.bridge_version,
            "data_scope": "status_and_provider_metadata_only",
        }
