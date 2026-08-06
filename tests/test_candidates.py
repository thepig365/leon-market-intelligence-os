import pytest

from lmio.candidates import transition_candidate
from lmio.domain import CandidateState, Strategy


def test_candidate_state_transition_records_evidence() -> None:
    event = transition_candidate(
        symbol="META",
        strategy=Strategy.QUALITY_GROWTH_MOMENTUM,
        previous_state=CandidateState.DISCOVERED,
        new_state=CandidateState.FILTERED,
        reason="Passed deterministic filter.",
        actor="screening-agent",
        evidence_urls=["https://www.sec.gov/example"],
        run_id="test-run",
    )

    assert event.new_state is CandidateState.FILTERED
    assert event.actor == "screening-agent"


def test_candidate_state_cannot_skip_research() -> None:
    with pytest.raises(ValueError, match="invalid candidate transition"):
        transition_candidate(
            symbol="META",
            strategy=Strategy.QUALITY_GROWTH_MOMENTUM,
            previous_state=CandidateState.FILTERED,
            new_state=CandidateState.CONFIRMED,
            reason="skip",
            actor="test",
            evidence_urls=[],
            run_id="test-run",
        )
