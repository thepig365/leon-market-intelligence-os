from lmio.replay import REPLAY_CASES, qualifies


def test_all_required_historical_failure_modes_are_covered() -> None:
    assert {case.name for case in REPLAY_CASES} == {
        "earnings_beat_continuation",
        "earnings_beat_sell_the_news",
        "guidance_cut",
        "merger_announcement",
        "form4_cluster_purchase",
        "13d_activist_filing",
        "high_short_interest_no_squeeze",
        "options_hedge_misclassification",
        "false_social_rumour",
    }
    assert all(qualifies(case) is case.expected_plan for case in REPLAY_CASES)
