from datetime import UTC, datetime

from lmio.demo import demo_universe, meta_acceptance_input
from lmio.domain import DataProvenance, NewsEvent
from lmio.research import build_research_pack
from lmio.screens import run_core_screens
from lmio.top3 import evaluate_top3
from lmio.valuation import run_valuation


def authorised_candidates():
    snapshots = [
        item.model_copy(update={"provenance": DataProvenance.HISTORICAL_AUTHORISED})
        for item in demo_universe()
    ]
    return run_core_screens(snapshots)


def test_top3_returns_structured_blocking_reasons_instead_of_silent_empty() -> None:
    selected, status = evaluate_top3(authorised_candidates(), {}, {})

    assert selected == []
    assert status.available is False
    assert status.message.startswith("Top 3 unavailable")
    assert status.reason_counts["missing authorised valuation inputs"] > 0
    assert status.reason_counts["15-field research package is pending"] > 0
    assert "refresh authorised financial evidence" in status.next_required_actions[0]


def test_top3_selects_only_after_valuation_and_research_gates_pass() -> None:
    candidate = next(item for item in authorised_candidates() if item.symbol == "META")
    valuation_input = meta_acceptance_input().model_copy(
        update={"provenance": DataProvenance.HISTORICAL_AUTHORISED}
    )
    valuation = run_valuation(valuation_input)
    news = [
        NewsEvent(
            headline="Authorised company update",
            source="Company IR",
            source_url="https://example.test/meta/update",
            source_tier=1,
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
            symbols=["META"],
            event_type="company_update",
            significance=80,
            surprise=10,
            confidence=0.9,
        )
    ]
    research = build_research_pack(candidate, news, valuation)

    selected, status = evaluate_top3(
        [candidate],
        {"META": valuation},
        {"META": research},
    )

    assert [item.symbol for item in selected] == ["META"]
    assert status.available is True
    assert status.evaluations[0].state == "top3_selected"
    assert status.evaluations[0].valuation_applicability == "applicable"
    assert status.evaluations[0].research_completeness == 1
