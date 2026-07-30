"""Historical replay expectations for known event failure modes."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplayCase:
    name: str
    official_evidence: bool
    price_confirmation: bool
    independent_confirmation: bool
    expected_plan: bool
    reason: str


REPLAY_CASES = (
    ReplayCase("earnings_beat_continuation", True, True, True, True, "confirmed continuation"),
    ReplayCase("earnings_beat_sell_the_news", True, False, True, False, "price failed"),
    ReplayCase("guidance_cut", True, True, True, True, "material official negative event"),
    ReplayCase("merger_announcement", True, True, True, True, "official deal event"),
    ReplayCase("form4_cluster_purchase", True, True, True, True, "official insider cluster"),
    ReplayCase("13d_activist_filing", True, True, True, True, "official activist filing"),
    ReplayCase(
        "high_short_interest_no_squeeze",
        True,
        False,
        False,
        False,
        "no price confirmation",
    ),
    ReplayCase("options_hedge_misclassification", False, True, False, False, "unverified intent"),
    ReplayCase("false_social_rumour", False, True, False, False, "no official evidence"),
)


def qualifies(case: ReplayCase) -> bool:
    return case.official_evidence and case.price_confirmation and case.independent_confirmation
