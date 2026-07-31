from datetime import UTC, datetime
from pathlib import Path

from lmio.config import Settings
from lmio.domain import NewsEvent, SecuritySnapshot
from lmio.news import event_fingerprint
from lmio.service import LMIOService


def test_daily_run_is_append_only_and_reproducible(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    first = service.run_demo_daily()
    second = service.run_demo_daily()
    counts = service.store.counts()

    assert first["top_10"] == second["top_10"]
    assert len(first["decision_cards"]) == 1
    assert first["decision_cards"][0]["symbol"] == "META"
    assert first["decision_cards"][0]["strict_fcf_value"] is not None
    assert first["decision_cards"][0]["owner_earnings_value"] is not None
    assert first["decision_cards"][0]["multi_model_value"] is not None
    assert counts["universe_runs"] == 2
    assert counts["screen_runs"] == 2
    assert counts["reports"] == 2
    assert counts["provider_snapshots"] == 7
    assert counts["symbols"] == 7
    assert counts["candidate_transitions"] >= 2
    history = service.store.history_json("reports")
    assert len(history) == 2
    assert history[0]["payload"]["data_mode"] == "synthetic_replay"


def test_meta_valuation_is_versioned(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    result = service.run_meta_acceptance()

    assert result["symbol"] == "META"
    assert service.store.counts()["valuation_runs"] == 1
    assert service.store.counts()["research_packs"] == 0
    assert service.store.counts()["conditional_plans"] == 0


def test_authorised_snapshot_never_reuses_synthetic_market_regime(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    snapshots = service.run_demo_daily()
    source_items = service.store.latest_json("universe_runs")
    assert source_items is not None

    report = service.run_daily(
        [SecuritySnapshot.model_validate(item) for item in source_items],
        data_mode="finviz_elite_csv",
    )

    assert report["regime"]["label"] == "Unverified"
    assert report["regime"]["confidence"] == 0
    assert report["regime"]["manual_review_required"] is True
    assert report["warnings"] == [
        "当前使用授权导出快照，不是持续实时数据流；市场状态与估值仍需独立验证。"
    ]
    assert "SPY +0.70%" not in str(report)
    assert snapshots["regime"]["label"] == "Risk-On"


def test_latest_candidates_produce_versioned_research_packs(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    service.run_demo_daily()

    packs = service.research_latest(limit=3)

    assert len(packs) == 3
    assert service.store.counts()["research_packs"] == 3
    meta = next(pack for pack in packs if pack["symbol"] == "META")
    assert "Multi-model base" in str(meta["valuation_summary"])


def test_master_spec_minimum_tables_exist(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    required = {
        "symbols",
        "symbol_classifications",
        "market_prices_daily",
        "market_prices_intraday",
        "market_indicators",
        "fundamentals",
        "financial_statements",
        "earnings_events",
        "earnings_estimates",
        "earnings_revisions",
        "news_events",
        "news_sources",
        "news_symbol_links",
        "sec_filings",
        "institutional_managers",
        "institutional_holdings",
        "insider_transactions",
        "short_interest",
        "options_flow",
        "social_mentions",
        "market_regimes",
        "screen_definitions",
        "screen_runs",
        "screen_results",
        "stock_candidates",
        "candidate_evidence",
        "valuation_runs",
        "valuation_assumptions",
        "valuation_results",
        "signal_scores",
        "trade_plans",
        "trade_plan_transitions",
        "paper_trades",
        "paper_trade_events",
        "telegram_deliveries",
        "reports",
        "strategy_performance",
        "provider_health",
        "system_events",
        "user_feedback",
    }
    with service.store.connection() as connection:
        actual = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert required <= actual


def test_news_event_can_be_retrieved_by_stable_fingerprint(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    event = NewsEvent(
        headline="Company raises official guidance",
        source="Company IR",
        source_url="https://example.test/investor-relations/guidance",
        source_tier=1,
        published_at=datetime(2026, 7, 30, tzinfo=UTC),
        symbols=["TEST"],
        event_type="guidance",
        significance=90,
        surprise=25,
        confidence=0.95,
    )
    fingerprint = event_fingerprint(event)

    assert service.store.put_news_event(fingerprint, event.model_dump(mode="json")) is True
    assert service.store.news_event(fingerprint) == event.model_dump(mode="json")
    assert service.store.news_event("missing") is None
