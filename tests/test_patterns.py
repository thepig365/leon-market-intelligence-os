from lmio.domain import PatternStage, PatternType
from lmio.patterns import build_pattern_signal, normalise_pattern


def test_approved_finviz_patterns_are_normalised() -> None:
    assert normalise_pattern("Ascending Triangle") is PatternType.ASCENDING_TRIANGLE
    assert normalise_pattern("Double Bottom") is PatternType.DOUBLE_BOTTOM
    assert normalise_pattern("Channel Up") is PatternType.TREND_PULLBACK
    assert normalise_pattern("Horizontal Resistance") is PatternType.BASE_BREAKOUT


def test_unapproved_pattern_is_not_promoted() -> None:
    assert normalise_pattern("Head & Shoulders") is None
    assert normalise_pattern(None) is None


def test_pattern_signal_waits_for_confirmation() -> None:
    result = build_pattern_signal("Double Bottom")

    assert result is not None
    assert result.pattern_type is PatternType.DOUBLE_BOTTOM
    assert result.stage is PatternStage.AWAITING_CONFIRMATION
    assert result.name_zh == "双底"
    assert "颈线" in result.confirmation
