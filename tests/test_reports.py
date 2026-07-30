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
