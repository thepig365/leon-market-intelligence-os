"""Audited candidate lifecycle with no implicit state jumps."""

from lmio.domain import CandidateState, CandidateTransition, Strategy

ALLOWED_CANDIDATE_TRANSITIONS = {
    CandidateState.DISCOVERED: {CandidateState.FILTERED, CandidateState.REJECTED},
    CandidateState.FILTERED: {
        CandidateState.RESEARCHING,
        CandidateState.REJECTED,
        CandidateState.EXPIRED,
    },
    CandidateState.RESEARCHING: {
        CandidateState.WATCHING,
        CandidateState.REJECTED,
        CandidateState.EXPIRED,
    },
    CandidateState.WATCHING: {
        CandidateState.CONFIRMED,
        CandidateState.REJECTED,
        CandidateState.EXPIRED,
    },
    CandidateState.CONFIRMED: {CandidateState.EXPIRED},
    CandidateState.REJECTED: set(),
    CandidateState.EXPIRED: set(),
}


def transition_candidate(
    *,
    symbol: str,
    strategy: Strategy,
    previous_state: CandidateState,
    new_state: CandidateState,
    reason: str,
    actor: str,
    evidence_urls: list[str],
) -> CandidateTransition:
    if new_state not in ALLOWED_CANDIDATE_TRANSITIONS[previous_state]:
        raise ValueError(f"invalid candidate transition: {previous_state} -> {new_state}")
    if not reason.strip() or not actor.strip():
        raise ValueError("candidate transition requires actor and reason")
    return CandidateTransition(
        symbol=symbol,
        strategy=strategy,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        actor=actor,
        evidence_urls=evidence_urls,
    )
