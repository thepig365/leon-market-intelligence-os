from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from lmio.options import (
    OptionDataMode,
    OptionObservation,
    OptionRight,
    classify_option,
    parse_barchart_csv,
)


def observation(**updates: object) -> OptionObservation:
    values: dict[str, object] = {
        "symbol": "SPY",
        "expiry": date.today() + timedelta(days=30),
        "strike": 700,
        "right": OptionRight.CALL,
        "observed_at": datetime.now(UTC),
        "source": "ibkr_tws_paper_delayed",
        "source_url": "https://www.interactivebrokers.com/",
        "data_mode": OptionDataMode.DELAYED,
        "delay_minutes": 15,
        "underlying_price": 695,
        "bid": 5.00,
        "ask": 5.50,
        "last": 5.50,
        "volume": 1000,
        "open_interest": 200,
    }
    values.update(updates)
    return OptionObservation.model_validate(values)


def test_conservative_unusual_option_candidate_is_explainable() -> None:
    result = classify_option(observation())

    assert result["candidate"] is True
    assert result["volume_oi_ratio"] == 5
    assert result["spread_pct"] == 9.52
    assert result["indicative_sentiment"] == "bullish_indication"
    assert "机构意图" in result["research_warning"]


@pytest.mark.parametrize(
    ("updates", "blocked"),
    [
        ({"volume": 499}, "volume"),
        ({"open_interest": 99}, "open_interest"),
        ({"volume": 500, "open_interest": 500}, "volume_oi_ratio"),
        ({"bid": 1.0, "ask": 2.0, "last": 1.5}, "spread"),
        ({"expiry": date.today() + timedelta(days=2)}, "dte"),
    ],
)
def test_candidate_fails_closed_when_a_gate_is_missing(
    updates: dict[str, object], blocked: str
) -> None:
    result = classify_option(observation(**updates))

    assert result["candidate"] is False
    assert blocked in result["blocked_checks"]


def test_observation_rejects_sensitive_or_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        observation(account_id="DU123456")


def test_manual_barchart_csv_is_parsed_without_scraping() -> None:
    batch = parse_barchart_csv(
        "Symbol,Exp Date,Strike,Type,Bid,Ask,Last,Volume,Open Int,IV,Delta\n"
        f"SPY,{(datetime.now(UTC).date() + timedelta(days=14)).strftime('%m/%d/%y')},"
        "700,Call,5.00,5.50,5.50,1000,200,25%,0.42\n"
    )

    assert batch.source == "barchart_manual_csv"
    assert len(batch.observations) == 1
    assert batch.observations[0].implied_volatility == 0.25
    assert classify_option(batch.observations[0])["candidate"] is True
