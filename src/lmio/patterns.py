"""Small, explainable chart-pattern vocabulary for LMIO."""

import re

from lmio.domain import PatternSignal, PatternStage, PatternType

PATTERN_DETAILS: dict[PatternType, tuple[str, str, str, str]] = {
    PatternType.BASE_BREAKOUT: (
        "平台突破",
        "Base Breakout",
        "收盘有效突破平台阻力，并获得成交量放大确认",
        "突破后重新跌回原平台",
    ),
    PatternType.ASCENDING_TRIANGLE: (
        "上升三角形",
        "Ascending Triangle",
        "收盘突破顶部阻力，并获得成交量放大确认",
        "跌破逐步抬高的趋势支撑",
    ),
    PatternType.DOUBLE_BOTTOM: (
        "双底",
        "Double Bottom",
        "收盘突破双底颈线，并获得成交量放大确认",
        "跌破第二个底部",
    ),
    PatternType.TREND_PULLBACK: (
        "上升趋势回调",
        "Uptrend Pullback",
        "回调止跌后重新向上，并获得成交量恢复确认",
        "跌破最近的关键回调低点",
    ),
}

_PATTERN_ALIASES: tuple[tuple[PatternType, tuple[str, ...]], ...] = (
    (
        PatternType.ASCENDING_TRIANGLE,
        ("ascending triangle", "triangle ascending"),
    ),
    (
        PatternType.DOUBLE_BOTTOM,
        ("double bottom",),
    ),
    (
        PatternType.TREND_PULLBACK,
        (
            "channel up",
            "up channel",
            "trendline support",
            "tl support",
        ),
    ),
    (
        PatternType.BASE_BREAKOUT,
        (
            "base breakout",
            "horizontal resistance",
            "horizontal s r",
            "rectangle",
        ),
    ),
)


def normalise_pattern(value: str | None) -> PatternType | None:
    """Map an explicit provider label into one of four approved patterns."""
    if not value:
        return None
    normalised = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    for strategy, aliases in _PATTERN_ALIASES:
        if any(alias in normalised for alias in aliases):
            return strategy
    return None


def build_pattern_signal(value: str | None) -> PatternSignal | None:
    """Build a conservative observation without claiming an unverified breakout."""
    pattern_type = normalise_pattern(value)
    if pattern_type is None or value is None:
        return None
    name_zh, name_en, confirmation, invalidation = PATTERN_DETAILS[pattern_type]
    return PatternSignal(
        name_zh=name_zh,
        name_en=name_en,
        pattern_type=pattern_type,
        stage=PatternStage.AWAITING_CONFIRMATION,
        source_pattern=value.strip(),
        confirmation=confirmation,
        invalidation=invalidation,
    )
