"""Versioned domain models for deterministic LMIO calculations."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Strategy(StrEnum):
    QUALITY_GROWTH_MOMENTUM = "quality_growth_momentum"
    EARNINGS_REVISION_MOMENTUM = "earnings_revision_momentum"


class CandidateState(StrEnum):
    DISCOVERED = "discovered"
    SCREENED = "screened"
    RESEARCH_REQUIRED = "research_required"
    WATCHLIST = "watchlist"
    PRIORITY = "priority"
    REJECTED = "rejected"


class SecuritySnapshot(BaseModel):
    """Normalised point-in-time equity facts used by V1 screens."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    company: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    source_url: str | None = None
    price: float = Field(gt=0)
    market_cap_m: float = Field(gt=0)
    average_dollar_volume_m: float = Field(ge=0)
    country: str = "USA"
    exchange: str = "NASDAQ"
    is_common_stock: bool = True
    is_otc: bool = False
    revenue_growth_pct: float | None = None
    eps_growth_pct: float | None = None
    gross_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    roic_pct: float | None = None
    debt_to_equity: float | None = None
    fcf_margin_pct: float | None = None
    relative_strength_6m: float | None = None
    price_above_200d_pct: float | None = None
    earnings_revision_30d_pct: float | None = None
    earnings_surprise_pct: float | None = None
    relative_volume: float | None = None
    sector_strength: float | None = None
    data_completeness: float = Field(default=1.0, ge=0, le=1)


class EvidenceItem(BaseModel):
    kind: str
    summary: str
    source: str
    source_url: str | None = None
    observed_at: datetime
    confidence: float = Field(ge=0, le=1)


class DimensionScores(BaseModel):
    quality: float = Field(ge=0, le=100)
    valuation: float = Field(ge=0, le=100)
    opportunity: float = Field(ge=0, le=100)
    timing: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    calculation_version: str


class ScreenCandidate(BaseModel):
    symbol: str
    company: str
    strategy: Strategy
    state: CandidateState
    scores: DimensionScores
    total_score: float = Field(ge=0, le=100)
    market_price: float
    catalyst: str
    next_confirmation: str
    invalidation: str
    horizon: str
    evidence: list[EvidenceItem]
    missing_fields: list[str] = Field(default_factory=list)


class ValuationInput(BaseModel):
    symbol: str
    operating_cash_flow: float
    capex: float
    finance_lease_principal: float = 0
    maintenance_capex: float | None = None
    growth_capex: float | None = None
    sustainable_owner_earnings: float | None = None
    net_cash: float
    diluted_shares: float = Field(gt=0)
    growth_rate: float
    terminal_growth: float
    discount_rate: float
    forecast_years: int = Field(default=5, ge=1, le=15)
    market_price: float = Field(gt=0)
    source: str
    observed_at: datetime
    confidence: float = Field(default=0.8, ge=0, le=1)


class ValuationPerspective(BaseModel):
    name: str
    pessimistic: float
    base: float
    optimistic: float
    applicability: str
    warning: str | None = None


class ValuationResult(BaseModel):
    symbol: str
    strict_fcf: ValuationPerspective
    normalised_owner_earnings: ValuationPerspective
    multi_model_fair_value: ValuationPerspective
    safety_margin: float
    safety_label: str
    confidence: float
    assumptions: dict[str, float | int | str]
    sensitivity: list[dict[str, float]]
    calculation_version: str
    calculated_at: datetime


class NewsEvent(BaseModel):
    headline: str
    source: str
    source_url: str
    source_tier: int = Field(ge=1, le=3)
    published_at: datetime
    symbols: list[str]
    event_type: str
    significance: float = Field(ge=0, le=100)
    surprise: float = Field(ge=-100, le=100)
    confidence: float = Field(ge=0, le=1)


class MarketRegime(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
    observed_at: datetime


class DailyReport(BaseModel):
    generated_at: datetime
    data_mode: str
    regime: MarketRegime
    funnel: dict[str, int]
    top_10: list[ScreenCandidate]
    top_3: list[ScreenCandidate]
    message_zh: str
    qualified_trade_plans: int = 0
    warnings: list[str] = Field(default_factory=list)
