from datetime import UTC, datetime

from lmio.news_research import NEWS_RESEARCH_CATEGORIES, build_news_research_board


def event(event_type: str, headline: str = "Official release") -> dict[str, object]:
    return {
        "headline": headline,
        "source": "Official",
        "source_url": "https://example.test/source",
        "source_tier": 1,
        "published_at": datetime(2026, 8, 3, tzinfo=UTC).isoformat(),
        "symbols": [],
        "event_type": event_type,
        "significance": 90,
        "confidence": 1,
    }


def test_news_board_always_exposes_all_required_categories() -> None:
    board = build_news_research_board([])

    assert len(NEWS_RESEARCH_CATEGORIES) == 9
    assert len(board["coverage"]) == 9
    assert {item["status"] for item in board["coverage"]} == {"waiting_for_verified_release"}
    assert board["events"] == []


def test_news_board_adds_research_lenses_without_exposing_source_links() -> None:
    board = build_news_research_board(
        [
            event("macro_inflation_cpi", "Consumer Price Index release"),
            event("sec_10-q", "AAPL filed SEC Form 10-Q"),
            event("sec_4", "AAPL filed SEC Form 4"),
        ]
    )

    assert len(board["events"]) == 3
    for item in board["events"]:
        assert item["summary"]
        assert item["trading_focus"]
        assert item["investing_focus"]
        assert item["missing_information"]
        assert "source_url" not in item
        assert item["system_action"] == "进入研究流程；不创建或执行订单。"

    coverage = {item["code"]: item for item in board["coverage"]}
    assert coverage["cpi"]["status"] == "available"
    assert coverage["sec_earnings"]["status"] == "available"
    assert coverage["insider"]["status"] == "available"
