"""Versioned domain models for deterministic LMIO calculations."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Strategy(StrEnum):
    QUALITY_GROWTH_MOMENTUM = "quality_growth_momentum"
    EARNINGS_REVISION_MOMENTUM = "earnings_revision_momentum"
    INSTITUTIONAL_ACCUMULATION = "institutional_accumulation"
    ACTIVIST_CATALYST = "activist_catalyst"
    INSIDER_VALUE = "insider_value"
    QARP = "quality_at_reasonable_price"
    PEAD = "post_earnings_announcement_drift"
    NEWS_DRIVEN = "news_driven"
    OVERSOLD_REVERSAL = "oversold_reversal"
    SHORT_SQUEEZE = "short_squeeze"
    PATTERN_RECOGNITION = "pattern_recognition"


class DataProvenance(StrEnum):
    """Authoritative provenance classes carried by every analytical record."""

    LIVE_AUTHORISED = "live_authorised"
    HISTORICAL_AUTHORISED = "historical_authorised"
    MANUAL_AUTHORISED = "manual_authorised"
    SYNTHETIC_REPLAY = "synthetic_replay"
    TEST_FIXTURE = "test_fixture"

    @property
    def operational(self) -> bool:
        return self in {
            self.LIVE_AUTHORISED,
            self.HISTORICAL_AUTHORISED,
            self.MANUAL_AUTHORISED,
        }


class PatternType(StrEnum):
    BASE_BREAKOUT = "base_breakout"
    ASCENDING_TRIANGLE = "ascending_triangle"
    DOUBLE_BOTTOM = "double_bottom"
    TREND_PULLBACK = "trend_pullback"


class PatternStage(StrEnum):
    FORMING = "forming"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class PatternSignal(BaseModel):
    """Explainable chart-pattern observation; never an order instruction."""

    name_zh: str
    name_en: str
    pattern_type: PatternType
    stage: PatternStage
    source_pattern: str
    key_level: str = "等待历史价格数据"
    volume_confirmation: str = "等待成交量确认"
    confirmation: str
    invalidation: str


class CandidateState(StrEnum):
    DISCOVERED = "discovered"
    FILTERED = "filtered"
    RESEARCHING = "researching"
    WATCHING = "watching"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"

    # Compatibility names for persisted V1-foundation records.
    SCREENED = "filtered"
    RESEARCH_REQUIRED = "researching"
    WATCHLIST = "watching"
    PRIORITY = "confirmed"


class Top3EligibilityState(StrEnum):
    SCREENED = "screened"
    RESEARCH_PENDING = "research_pending"
    VALUATION_PENDING = "valuation_pending"
    EVIDENCE_INCOMPLETE = "evidence_incomplete"
    TOP3_ELIGIBLE = "top3_eligible"
    TOP3_SELECTED = "top3_selected"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SecuritySnapshot(BaseModel):
    """Normalised point-in-time equity facts used by V1 screens."""

    model_config = ConfigDict(frozen=True)

    symbol: str
    company: str
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    source_url: str | None = None
    provenance: DataProvenance = DataProvenance.TEST_FIXTURE
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
    forward_pe: float | None = None
    earnings_revision_breadth_pct: float | None = None
    institutional_ownership_change_pct: float | None = None
    activist_stake_pct: float | None = None
    insider_net_buying_m: float | None = None
    days_since_earnings: int | None = None
    post_earnings_return_pct: float | None = None
    rsi_14: float | None = None
    short_interest_float_pct: float | None = None
    days_to_cover: float | None = None
    borrow_cost_pct: float | None = None
    news_impact_score: float | None = None
    chart_pattern: str | None = None
    data_completeness: float = Field(default=1.0, ge=0, le=1)


class EvidenceItem(BaseModel):
    kind: str
    summary: str
    source: str
    source_url: str | None = None
    observed_at: datetime
    confidence: float = Field(ge=0, le=1)


class ScoreBreakdown(BaseModel):
    component_names: list[str]
    component_inputs: dict[str, float | None]
    component_weights: dict[str, float]
    missing_inputs: list[str] = Field(default_factory=list)
    penalties: dict[str, float] = Field(default_factory=dict)
    final_score: float = Field(ge=0, le=100)
    score_version: str
    evidence_references: list[str] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DimensionScores(BaseModel):
    quality: float = Field(ge=0, le=100)
    valuation: float = Field(ge=0, le=100)
    opportunity: float = Field(ge=0, le=100)
    timing: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    calculation_version: str
    breakdowns: dict[str, ScoreBreakdown] = Field(default_factory=dict)


class ScreenCandidate(BaseModel):
    symbol: str
    company: str
    provenance: DataProvenance = DataProvenance.TEST_FIXTURE
    strategy: Strategy
    state: CandidateState
    scores: DimensionScores
    total_score: float = Field(ge=0, le=100)
    market_price: float
    intrinsic_value_range: str = "待完成可复现估值"
    catalyst: str
    next_confirmation: str
    invalidation: str
    horizon: str
    evidence: list[EvidenceItem]
    missing_fields: list[str] = Field(default_factory=list)
    source_completeness: float = Field(default=0, ge=0, le=1)
    pattern: PatternSignal | None = None


class Top3Evaluation(BaseModel):
    symbol: str
    strategy: Strategy
    state: Top3EligibilityState
    strategy_match: bool
    scores: DimensionScores
    data_confidence: float = Field(ge=0, le=1)
    source_completeness: float = Field(ge=0, le=1)
    valuation_applicability: str
    research_completeness: float = Field(ge=0, le=1)
    catalyst: str
    supporting_evidence: list[str]
    contrary_evidence: list[str]
    next_confirmation: str
    invalidation_conditions: str
    blocked_reasons: list[str] = Field(default_factory=list)


class Top3Status(BaseModel):
    available: bool
    message: str
    reason_counts: dict[str, int] = Field(default_factory=dict)
    next_required_actions: list[str] = Field(default_factory=list)
    evaluations: list[Top3Evaluation] = Field(default_factory=list)


class CandidateTransition(BaseModel):
    symbol: str
    strategy: Strategy
    previous_state: CandidateState | None
    new_state: CandidateState
    reason: str
    actor: str
    evidence_urls: list[str] = Field(default_factory=list)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SignalRecord(BaseModel):
    signal_id: str
    symbol: str
    strategy: Strategy
    created_at: datetime
    signal_price: float = Field(gt=0)
    benchmark: str
    benchmark_price: float = Field(gt=0)
    source_snapshot_ids: list[str]
    scores: DimensionScores
    candidate_state: CandidateState
    plan_id: str
    invalidation_conditions: list[str]
    provenance: DataProvenance
    model_versions: dict[str, str]


class ValuationInput(BaseModel):
    symbol: str
    provenance: DataProvenance = DataProvenance.TEST_FIXTURE
    operating_cash_flow: float
    capex: float
    finance_lease_principal: float = 0
    maintenance_capex: float | None = None
    growth_capex: float | None = None
    sustainable_owner_earnings: float | None = None
    revenue: float | None = Field(default=None, gt=0)
    ebitda: float | None = Field(default=None, gt=0)
    net_income: float | None = None
    ev_revenue_multiple: float | None = Field(default=None, gt=0)
    ev_ebitda_multiple: float | None = Field(default=None, gt=0)
    pe_multiple: float | None = Field(default=None, gt=0)
    p_fcf_multiple: float | None = Field(default=None, gt=0)
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
    provenance: DataProvenance = DataProvenance.TEST_FIXTURE
    strict_fcf: ValuationPerspective
    normalised_owner_earnings: ValuationPerspective
    multi_model_fair_value: ValuationPerspective
    safety_margin: float
    safety_label: str
    confidence: float
    assumptions: dict[str, float | int | str | None]
    model_components: list[dict[str, float | str]]
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
    contrary_evidence: list[str] = Field(default_factory=list)
    preferred_strategies: list[Strategy] = Field(default_factory=list)
    suppressed_strategies: list[Strategy] = Field(default_factory=list)
    risk_multiplier: float = Field(default=1, ge=0, le=2)
    blocked_sectors: list[str] = Field(default_factory=list)
    blocked_symbols: list[str] = Field(default_factory=list)
    manual_review_required: bool = False
    observed_at: datetime


class DecisionCard(BaseModel):
    symbol: str
    company: str
    strategy: Strategy
    what_changed: str
    scores: DimensionScores
    market_price: float = Field(gt=0)
    strict_fcf_value: float | None = None
    owner_earnings_value: float | None = None
    multi_model_value: float | None = None
    intrinsic_value_range: str
    safety_margin: float | None = None
    valuation_confidence: float | None = Field(default=None, ge=0, le=1)
    supporting_evidence: list[str]
    contrary_evidence: list[str]
    risks: list[str]
    confirmation_condition: str
    entry_zone: str
    stop_reference: str
    target_reference: str
    risk_reward: float = Field(gt=0)
    status: str


class DailyReport(BaseModel):
    generated_at: datetime
    data_mode: str
    provenance: DataProvenance
    regime: MarketRegime
    funnel: dict[str, int]
    top_10: list[ScreenCandidate]
    top_3: list[ScreenCandidate]
    top_3_status: Top3Status
    decision_cards: list[DecisionCard] = Field(default_factory=list)
    message_zh: str
    qualified_trade_plans: int = 0
    warnings: list[str] = Field(default_factory=list)
