"""Daily ranking and quiet Chinese reporting."""

from datetime import UTC, datetime

from lmio.domain import DailyReport, MarketRegime, ScreenCandidate


def classify_regime(
    spy_return_pct: float,
    qqq_return_pct: float,
    iwm_return_pct: float,
    vix: float,
    breadth_pct: float,
    usd_jpy_change_pct: float | None = None,
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
    return MarketRegime(
        label=label,
        confidence=confidence,
        evidence=evidence,
        observed_at=datetime.now(UTC),
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
) -> DailyReport:
    ranked = _dedupe_symbols(candidates)
    top_10 = ranked[:10]
    top_3 = [item for item in top_10 if item.scores.confidence >= 0.75 and item.total_score >= 65][
        :3
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
    warnings = []
    if data_mode != "live":
        warnings.append("当前使用明确标注的演示/回放数据，不代表实时市场。")
    return DailyReport(
        generated_at=datetime.now(UTC),
        data_mode=data_mode,
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
        message_zh="\n".join(lines),
        warnings=warnings,
    )
