import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lmio.config import Settings
from lmio.demo import demo_universe
from lmio.domain import DataProvenance, NewsEvent, SecuritySnapshot
from lmio.news import event_fingerprint
from lmio.providers.official_rss import OfficialFeed, OfficialRSSProvider
from lmio.providers.sec import SECProvider
from lmio.service import MAX_OPERATIONAL_CANDIDATES, LMIOService


def authorised_snapshots() -> list[SecuritySnapshot]:
    return [
        item.model_copy(update={"provenance": DataProvenance.HISTORICAL_AUTHORISED})
        for item in demo_universe()
    ]


def test_synthetic_daily_run_is_isolated_and_reproducible(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    first = service.run_demo_daily()
    second = service.run_demo_daily()
    counts = service.store.counts()

    assert first["top_10"] == second["top_10"]
    assert first["provenance"] == "synthetic_replay"
    assert counts["universe_runs"] == 0
    assert counts["screen_runs"] == 0
    assert counts["reports"] == 0
    assert counts["provider_snapshots"] == 0
    assert counts["symbols"] == 0
    assert counts["candidate_transitions"] == 0
    assert counts["synthetic_records"] == 2
    history = service.store.history_json("synthetic_records")
    assert len(history) == 2
    assert history[0]["payload"]["report"]["data_mode"] == "synthetic_replay"
    assert service.store.latest_json("reports") is None
    assert service.store.latest_json("screen_runs") is None


def test_daily_run_rejects_mixed_provenance(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    snapshots = authorised_snapshots()
    snapshots[0] = snapshots[0].model_copy(
        update={"provenance": DataProvenance.SYNTHETIC_REPLAY}
    )

    with pytest.raises(ValueError, match="cannot mix provenance"):
        service.run_daily(snapshots, data_mode="invalid_mixed_input")

    assert service.store.counts()["universe_runs"] == 0
    assert service.store.counts()["synthetic_records"] == 0


def test_meta_valuation_is_versioned(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))

    result = service.run_meta_acceptance()

    assert result["symbol"] == "META"
    assert result["provenance"] == "synthetic_replay"
    assert service.store.counts()["valuation_runs"] == 0
    assert service.store.counts()["synthetic_records"] == 1
    assert service.store.counts()["research_packs"] == 0
    assert service.store.counts()["conditional_plans"] == 0


def test_authorised_snapshot_never_reuses_synthetic_market_regime(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    synthetic = service.run_demo_daily()

    report = service.run_daily(
        authorised_snapshots(),
        data_mode="finviz_elite_csv",
    )

    assert report["regime"]["label"] == "Unverified"
    assert report["provenance"] == "historical_authorised"
    assert report["regime"]["confidence"] == 0
    assert report["regime"]["manual_review_required"] is True
    assert report["warnings"] == [
        "当前使用授权导出快照，不是持续实时数据流；市场状态与估值仍需独立验证。"
    ]
    assert "SPY +0.70%" not in str(report)
    assert synthetic["regime"]["label"] == "Risk-On"
    assert service.store.counts()["reports"] == 1
    assert service.store.counts()["synthetic_records"] == 1


def test_authorised_refresh_persists_only_screen_candidates(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    service.run_daily(
        authorised_snapshots(),
        data_mode="finviz_elite_api",
    )

    candidate_symbols = {
        item["symbol"]
        for item in (service.store.latest_json("screen_runs") or [])[:MAX_OPERATIONAL_CANDIDATES]
    }
    stored_symbols = {
        item["symbol"]
        for item in service.store.history_json("provider_snapshots", limit=100)
        if item["provider"] == "finviz_elite_api"
    }
    assert stored_symbols == candidate_symbols


def test_latest_candidates_produce_versioned_research_packs(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    service.run_daily(authorised_snapshots(), data_mode="authorised_fixture")

    packs = service.research_latest(limit=3)

    assert len(packs) == 3
    assert service.store.counts()["research_packs"] == 3
    assert {pack["model_version"] for pack in packs} == {"deterministic-research-pack-v2"}


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


def test_news_refresh_expands_sec_watchlist_from_latest_top_ten(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "runtime.sqlite3",
        sec_user_agent="LMIO research admin@example.test",
        sec_watchlist="AAPL:320193,META:1326801",
    )
    service = LMIOService(settings)
    service.store.append_json(
        "reports",
        {
            "report_type": "daily",
            "payload": {"top_10": [{"symbol": "TEST"}]},
        },
    )
    feed = OfficialFeed(
        name="test_feed",
        url="https://www.bls.gov/feed/test.rss",
        source="U.S. Bureau of Labor Statistics",
        event_type="macro_test",
        significance=90,
    )
    rss = b"""
        <rss version="2.0"><channel><item>
        <title>Official release</title>
        <link>https://www.bls.gov/news.release/test.htm</link>
        <pubDate>Fri, 31 Jul 2026 08:30:00 -0400</pubDate>
        </item></channel></rss>
    """

    def sec_transport(url: str, _headers: dict[str, str]) -> bytes:
        if url.endswith("company_tickers.json"):
            return json.dumps(
                {"0": {"cik_str": 1234567, "ticker": "TEST", "title": "Test Inc."}}
            ).encode()
        cik = url.rsplit("CIK", 1)[-1].removesuffix(".json")
        return json.dumps(
            {
                "cik": cik,
                "filings": {
                    "recent": {
                        "accessionNumber": [],
                        "filingDate": [],
                        "form": [],
                        "primaryDocument": [],
                    }
                },
            }
        ).encode()

    result = service.refresh_official_news(
        macro_provider=OfficialRSSProvider((feed,), lambda *_: rss),
        sec_provider=SECProvider(settings.sec_user_agent, sec_transport),
    )

    assert result["macro"]["inserted"] == 1
    assert result["sec"]["symbols"] == 3
    assert result["sec"]["unresolved_symbols"] == 0


def test_latest_news_uses_publication_time_not_ingestion_order(tmp_path: Path) -> None:
    service = LMIOService(Settings(_env_file=None, database_path=tmp_path / "runtime.sqlite3"))
    newer = NewsEvent(
        headline="Newer release",
        source="Official",
        source_url="https://example.test/newer",
        source_tier=1,
        published_at=datetime(2026, 7, 31, tzinfo=UTC),
        symbols=[],
        event_type="macro_test",
        significance=70,
        surprise=0,
        confidence=1,
    )
    older = newer.model_copy(
        update={
            "headline": "Older release ingested later",
            "source_url": "https://example.test/older",
            "published_at": datetime(2026, 7, 30, tzinfo=UTC),
            "significance": 99,
        }
    )
    service.store.put_news_event(event_fingerprint(newer), newer.model_dump(mode="json"))
    service.store.put_news_event(event_fingerprint(older), older.model_dump(mode="json"))

    assert [item["headline"] for item in service.latest_news(2)] == [
        "Newer release",
        "Older release ingested later",
    ]
