from lmio.demo import demo_universe
from lmio.reports import build_daily_report, classify_regime
from lmio.screens import run_core_screens
from lmio.universe import build_investable_universe


def test_report_deduplicates_symbols_and_is_chinese() -> None:
    universe = build_investable_universe(demo_universe())
    report = build_daily_report(
        run_core_screens(universe),
        len(demo_universe()),
        len(universe),
        classify_regime(1, 1, 0.8, 18, 60),
        data_mode="synthetic_replay",
    )

    symbols = [item.symbol for item in report.top_10]
    assert len(symbols) == len(set(symbols))
    assert "盘前研究简报" in report.message_zh
    assert "不会执行交易" in report.message_zh
    assert report.warnings


def test_rapid_yen_strengthening_preserves_macro_shock_hypothesis() -> None:
    regime = classify_regime(0, 0, 0, 20, 50, usd_jpy_change_pct=-2.5)

    assert regime.label == "Macro Shock"
    assert "USD/JPY -2.50%" in regime.evidence


def test_market_regime_exposes_strategy_and_risk_controls() -> None:
    regime = classify_regime(
        -1.5,
        -1.8,
        -2,
        32,
        28,
        treasury_10y_change_bps=12,
        dxy_change_pct=0.8,
        oil_change_pct=-2,
        gold_change_pct=1.2,
        macro_events=["FOMC"],
    )

    assert regime.risk_multiplier < 1
    assert regime.suppressed_strategies
    assert regime.manual_review_required is True
