"""Daily ranking and quiet Chinese reporting."""

from datetime import UTC, datetime

from lmio.domain import (
    DailyReport,
    DataProvenance,
    DecisionCard,
    MarketRegime,
    ScreenCandidate,
    Strategy,
    ValuationResult,
)


def classify_regime(
    spy_return_pct: float,
    qqq_return_pct: float,
    iwm_return_pct: float,
    vix: float,
    breadth_pct: float,
    usd_jpy_change_pct: float | None = None,
    treasury_10y_change_bps: float | None = None,
    dxy_change_pct: float | None = None,
    oil_change_pct: float | None = None,
    gold_change_pct: float | None = None,
    sector_leaders: list[str] | None = None,
    macro_events: list[str] | None = None,
) -> MarketRegime:
    evidence = [
        f"SPY {spy_return_pct:+.2f}%",
        f"QQQ {qqq_return_pct:+.2f}%",
        f"IWM {iwm_return_pct:+.2f}%",
        f"VIX {vix:.1f}",
        f"上涨广度 {breadth_pct:.1f}%",
    ]
    if usd_jpy_change_pct is not None:
        evidence.append(f"USD/JPY {usd_jpy_change_pct:+.2f}%")
    if treasury_10y_change_bps is not None:
        evidence.append(f"美国10年期收益率 {treasury_10y_change_bps:+.1f}bp")
    if dxy_change_pct is not None:
        evidence.append(f"DXY {dxy_change_pct:+.2f}%")
    if oil_change_pct is not None:
        evidence.append(f"原油 {oil_change_pct:+.2f}%")
    if gold_change_pct is not None:
        evidence.append(f"黄金 {gold_change_pct:+.2f}%")
    if sector_leaders:
        evidence.append(f"领涨板块 {', '.join(sector_leaders)}")
    if macro_events:
        evidence.append(f"宏观事件 {', '.join(macro_events)}")
    average = (spy_return_pct + qqq_return_pct + iwm_return_pct) / 3
    if usd_jpy_change_pct is not None and usd_jpy_change_pct <= -2:
        label = "Macro Shock"
        confidence = 0.85
    elif vix >= 30:
        label = "High Volatility"
        confidence = 0.9
    elif average <= -1 and breadth_pct < 40:
        label = "Risk-Off"
        confidence = 0.8
    elif average >= 0.5 and breadth_pct > 55:
        label = "Risk-On"
        confidence = 0.8
    elif vix < 15:
        label = "Low Volatility"
        confidence = 0.75
    else:
        label = "Range"
        confidence = 0.65
    defensive = {
        Strategy.QUALITY_GROWTH_MOMENTUM,
        Strategy.QARP,
        Strategy.INSIDER_VALUE,
    }
    tactical = {
        Strategy.EARNINGS_REVISION_MOMENTUM,
        Strategy.PEAD,
        Strategy.NEWS_DRIVEN,
        Strategy.INSTITUTIONAL_ACCUMULATION,
    }
    contrary: list[str] = []
    manual_review = False
    blocked_sectors: list[str] = []
    if average > 0 and breadth_pct < 40:
        contrary.append("指数上涨但市场广度偏弱")
    if vix >= 30 and average > 0:
        contrary.append("指数上涨与高波动并存")
    if macro_events:
        manual_review = True
    if label in {"Macro Shock", "High Volatility", "Risk-Off"}:
        preferred = sorted(defensive, key=str)
        suppressed = sorted(
            {
                Strategy.OVERSOLD_REVERSAL,
                Strategy.SHORT_SQUEEZE,
                Strategy.NEWS_DRIVEN,
            },
            key=str,
        )
        risk_multiplier = 0.5 if label != "Risk-Off" else 0.7
    elif label == "Risk-On":
        preferred = sorted(tactical, key=str)
        suppressed = []
        risk_multiplier = 1
    else:
        preferred = sorted(defensive | tactical, key=str)
        suppressed = [Strategy.SHORT_SQUEEZE]
        risk_multiplier = 0.8
    return MarketRegime(
        label=label,
        confidence=confidence,
        evidence=evidence,
        contrary_evidence=contrary,
        preferred_strategies=preferred,
        suppressed_strategies=suppressed,
        risk_multiplier=risk_multiplier,
        blocked_sectors=blocked_sectors,
        manual_review_required=manual_review,
        observed_at=datetime.now(UTC),
    )


def unverified_regime(observed_at: datetime | None = None) -> MarketRegime:
    """Return a fail-safe regime when benchmark evidence is unavailable."""

    return MarketRegime(
        label="Unverified",
        confidence=0,
        evidence=["当前数据源未提供可验证的 SPY、QQQ、IWM、VIX 与市场广度输入"],
        contrary_evidence=[],
        preferred_strategies=[],
        suppressed_strategies=[],
        risk_multiplier=0,
        blocked_sectors=[],
        blocked_symbols=[],
        manual_review_required=True,
        observed_at=observed_at or datetime.now(UTC),
    )


def _dedupe_symbols(candidates: list[ScreenCandidate]) -> list[ScreenCandidate]:
    selected: dict[str, ScreenCandidate] = {}
    for candidate in candidates:
        current = selected.get(candidate.symbol)
        if current is None or candidate.total_score > current.total_score:
            selected[candidate.symbol] = candidate
    return sorted(selected.values(), key=lambda item: (-item.total_score, item.symbol))


def build_daily_report(
    candidates: list[ScreenCandidate],
    universe_checked: int,
    investable: int,
    regime: MarketRegime,
    *,
    data_mode: str,
    valuations: dict[str, ValuationResult] | None = None,
    provenance: DataProvenance = DataProvenance.TEST_FIXTURE,
) -> DailyReport:
    valuation_map = valuations or {}
    ranked = [
        item.model_copy(
            update={
                "intrinsic_value_range": (
                    f"{valuation_map[item.symbol].multi_model_fair_value.pessimistic:.2f}"
                    f"–{valuation_map[item.symbol].multi_model_fair_value.optimistic:.2f}"
                )
            }
        )
        if item.symbol in valuation_map
        else item
        for item in _dedupe_symbols(candidates)
    ]
    top_10 = ranked[:10]
    top_3 = [
        item
        for item in top_10
        if item.scores.confidence >= 0.75
        and item.total_score >= 65
        and item.symbol in valuation_map
    ][:3]
    decision_cards = [
        DecisionCard(
            symbol=item.symbol,
            company=item.company,
            strategy=item.strategy,
            what_changed=item.catalyst,
            scores=item.scores,
            market_price=item.market_price,
            strict_fcf_value=valuation_map[item.symbol].strict_fcf.base,
            owner_earnings_value=valuation_map[item.symbol].normalised_owner_earnings.base,
            multi_model_value=valuation_map[item.symbol].multi_model_fair_value.base,
            intrinsic_value_range=item.intrinsic_value_range,
            safety_margin=valuation_map[item.symbol].safety_margin,
            valuation_confidence=valuation_map[item.symbol].confidence,
            supporting_evidence=[evidence.summary for evidence in item.evidence],
            contrary_evidence=(
                [f"缺失字段：{', '.join(item.missing_fields)}"] if item.missing_fields else []
            ),
            risks=[item.invalidation],
            confirmation_condition=item.next_confirmation,
            entry_zone="仅在确认条件满足后计算；当前不构成交易指令",
            stop_reference=item.invalidation,
            target_reference="完成估值与价格结构确认后计算",
            risk_reward=2,
            status="research_only",
        )
        for item in top_3
    ]
    lines = [
        "LMIO 美股盘前研究简报",
        f"市场状态：{regime.label}（置信度 {regime.confidence:.0%}）",
        (
            f"漏斗：检查 {universe_checked}｜可投资 {investable}｜"
            f"异常候选 {len(candidates)}｜观察名单 {len(top_10)}｜优先机会 {len(top_3)}"
        ),
    ]
    if top_3:
        lines.append("优先研究：")
        lines.extend(
            f"{index}. {item.symbol}｜{item.catalyst}｜总分 {item.total_score:.1f}"
            for index, item in enumerate(top_3, start=1)
        )
    else:
        lines.append("今日没有符合标准的交易计划。")
    lines.append("说明：这是研究与决策支持，不构成投资建议，也不会执行交易。")
    warnings: list[str] = []
    if data_mode == "synthetic_replay":
        warnings.append("当前使用明确标注的演示/回放数据，不代表实时市场。")
    elif data_mode != "live":
        warnings.append("当前使用授权导出快照，不是持续实时数据流；市场状态与估值仍需独立验证。")
    return DailyReport(
        generated_at=datetime.now(UTC),
        data_mode=data_mode,
        provenance=provenance,
        regime=regime,
        funnel={
            "universe_checked": universe_checked,
            "investable": investable,
            "abnormal_candidates": len(candidates),
            "researched": 0,
            "watchlist": len(top_10),
            "priority_opportunities": len(top_3),
            "qualified_trade_plans": 0,
        },
        top_10=top_10,
        top_3=top_3,
        decision_cards=decision_cards,
        message_zh="\n".join(lines),
        warnings=warnings,
    )
