import json
from datetime import date
from urllib.request import Request

import pytest
from pydantic import ValidationError

from lmio.providers import (
    OpenAINewsWorker,
    OpenAIOptionsScreenshotWorker,
    OpenAIResearchWorker,
    ProviderState,
    build_kimi_manual_packet,
    validate_kimi_manual_output,
)


def synthesis_payload() -> dict[str, object]:
    return {
        "symbol": "META",
        "summary": "Margins improved in the supplied filing.",
        "thesis": "Evidence supports further review.",
        "supporting_evidence": ["Reported margin improved."],
        "contrary_evidence": ["Capital expenditure remains high."],
        "risks": ["Guidance may change."],
        "missing_information": ["No current market price supplied."],
        "source_urls": ["https://www.sec.gov/example"],
        "confidence": 0.72,
    }


def test_openai_worker_is_inert_without_configuration() -> None:
    worker = OpenAIResearchWorker(api_key="", model="")

    assert worker.health().state is ProviderState.DISABLED
    with pytest.raises(RuntimeError, match="disabled"):
        worker.analyse({"symbol": "META"})


def test_openai_worker_sends_minimal_server_side_structured_request() -> None:
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> dict[str, object]:
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.data or b"{}")
        return {"output_text": json.dumps(synthesis_payload())}

    worker = OpenAIResearchWorker(
        api_key="secret-test-key",
        model="approved-model-snapshot",
        transport=transport,
    )

    assert worker.health().state is ProviderState.CONFIGURED_NOT_VERIFIED
    result = worker.analyse({"symbol": "META", "source_urls": ["https://www.sec.gov/example"]})

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["store"] is False
    assert body["model"] == "approved-model-snapshot"
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["schema"]["additionalProperties"] is False
    assert "tools" not in body
    assert "previous_response_id" not in body
    assert captured["authorization"] == "Bearer secret-test-key"
    assert result["order_created"] is False
    assert result["provider"] == "openai_research"


def test_openai_news_worker_uses_no_tools_and_reports_usage() -> None:
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> dict[str, object]:
        captured["body"] = json.loads(request.data or b"{}")
        return {
            "output_text": json.dumps(
                {
                    "summary": "官方事件元数据已记录。",
                    "trading_focus": "核对价格和成交量反应。",
                    "investing_focus": "核对长期现金流影响。",
                    "missing_information": "未提供具体披露数字。",
                    "confidence": 0.6,
                }
            ),
            "usage": {"input_tokens": 120, "output_tokens": 80},
        }

    worker = OpenAINewsWorker(
        api_key="secret-test-key",
        model="gpt-5.6-luna",
        transport=transport,
    )
    result = worker.analyse(
        {
            "headline": "Official release",
            "event_type": "macro_inflation_cpi",
            "source": "BLS",
        }
    )

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["store"] is False
    assert body["model"] == "gpt-5.6-luna"
    assert body["max_output_tokens"] == 500
    assert body["reasoning"] == {"effort": "low"}
    assert "tools" not in body
    assert "source_url" not in body["input"]
    assert result["usage"] == {"input_tokens": 120, "output_tokens": 80}
    assert result["order_created"] is False


def test_openai_options_screenshot_worker_is_tool_free_and_does_not_store_image() -> None:
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> dict[str, object]:
        captured["body"] = json.loads(request.data or b"{}")
        return {
            "output_text": json.dumps(
                {
                    "plain_language_summary": "截图显示 AAPL Call 成交兴趣，但不能证明开仓。",
                    "alerts": [
                        {
                            "symbol": "AAPL",
                            "trade_date": "2026-08-07",
                            "trade_time": "5:22 am",
                            "expiry": "2026-08-10",
                            "days_to_expiry": None,
                            "strike": 317.5,
                            "right": "call",
                            "contracts": 6964,
                            "trade_price": 1.5,
                            "bid_price": None,
                            "ask_price": None,
                            "source_action_label": "bought",
                            "aggressor_side": "buy",
                            "aggressor_method": "explicit_label",
                            "aggressor_basis": "截图明确写有 BOUGHT。",
                            "open_interest": 3474,
                            "total_premium_usd": 1044182,
                            "volume_oi_ratio": 2.0,
                            "extraction_confidence": 0.98,
                        }
                    ],
                    "notable_patterns": ["Call 成交量高于现有 OI。"],
                    "bullish_clues": ["Call 买入兴趣。"],
                    "bearish_clues": [],
                    "what_this_does_not_prove": ["不能证明为新开多仓。"],
                    "confirmation_checks": ["核对次日 OI 与标的走势。"],
                    "ticker_assessments": [
                        {
                            "symbol": "AAPL",
                            "flow_bias": "bullish_interest",
                            "why_notable": "Call 成交量较高。",
                            "confirmation_needed": "核对成交方向与次日 OI。",
                            "invalidation_or_risk": "可能是平仓或组合对冲。",
                            "research_stance": "wait_for_confirmation",
                        }
                    ],
                    "overall_confidence": 0.8,
                }
            ),
            "usage": {"input_tokens": 900, "output_tokens": 300},
        }

    worker = OpenAIOptionsScreenshotWorker(
        api_key="server-secret",
        model="gpt-5.6-luna",
        transport=transport,
        today=lambda: date(2026, 8, 7),
    )
    result = worker.analyse("data:image/png;base64,iVBORw0KGgo=")

    body = captured["body"]
    assert isinstance(body, dict)
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "low"}
    assert "tools" not in body
    image = body["input"][0]["content"][1]
    assert image["type"] == "input_image"
    assert image["detail"] == "high"
    assert image["image_url"].startswith("data:image/png;base64,")
    assert result["alerts"][0]["days_to_expiry"] == 3
    assert result["alerts"][0]["trade_date"] == "2026-08-07"
    assert result["alerts"][0]["trade_time"] == "5:22 am"
    assert result["alerts"][0]["aggressor_side"] == "buy"
    assert result["alerts"][0]["aggressor_method"] == "explicit_label"
    assert result["alerts"][0]["trade_price"] == 1.5
    assert result["order_created"] is False
    assert result["execution_allowed"] is False
    assert result["usage"] == {"input_tokens": 900, "output_tokens": 300}


def test_options_screenshot_uses_trade_date_and_quote_position_without_guessing() -> None:
    alerts = [
        {
            "symbol": "ASK",
            "trade_date": "2026-08-05",
            "trade_time": "10:15 am",
            "expiry": "2026-08-14",
            "days_to_expiry": None,
            "strike": 100,
            "right": "call",
            "contracts": 500,
            "trade_price": 1.25,
            "bid_price": 1.15,
            "ask_price": 1.25,
            "source_action_label": "none",
            "aggressor_side": "unknown",
            "aggressor_method": "unknown",
            "aggressor_basis": "模型初稿不得决定。",
            "open_interest": 100,
            "total_premium_usd": 62500,
            "volume_oi_ratio": 5,
            "extraction_confidence": 0.9,
        },
        {
            "symbol": "MID",
            "trade_date": None,
            "trade_time": "10:16 am",
            "expiry": "2026-08-14",
            "days_to_expiry": None,
            "strike": 100,
            "right": "put",
            "contracts": 500,
            "trade_price": 1.20,
            "bid_price": 1.15,
            "ask_price": 1.25,
            "source_action_label": "none",
            "aggressor_side": "buy",
            "aggressor_method": "quote_position",
            "aggressor_basis": "模型不应猜测。",
            "open_interest": 100,
            "total_premium_usd": 60000,
            "volume_oi_ratio": 5,
            "extraction_confidence": 0.9,
        },
    ]

    def transport(request: Request, timeout: float) -> dict[str, object]:
        request_body = json.loads(request.data or b"{}")
        input_text = request_body["input"][0]["content"][0]["text"]
        assert "analysis_date 为 2026-08-07" in input_text
        return {
            "output_text": json.dumps(
                {
                    "plain_language_summary": "按截图事实分析。",
                    "alerts": alerts,
                    "notable_patterns": [],
                    "bullish_clues": [],
                    "bearish_clues": [],
                    "what_this_does_not_prove": ["不能证明开仓。"],
                    "confirmation_checks": ["核对次日 OI。"],
                    "ticker_assessments": [],
                    "overall_confidence": 0.7,
                }
            )
        }

    worker = OpenAIOptionsScreenshotWorker(
        api_key="server-secret",
        model="gpt-5.6-luna",
        transport=transport,
        today=lambda: date(2026, 8, 7),
    )
    result = worker.analyse("data:image/png;base64,iVBORw0KGgo=")

    ask, middle = result["alerts"]
    assert ask["days_to_expiry"] == 9
    assert ask["aggressor_side"] == "buy"
    assert ask["aggressor_method"] == "quote_position"
    assert "Ask" in ask["aggressor_basis"]
    assert middle["days_to_expiry"] == 7
    assert middle["aggressor_side"] == "unknown"
    assert middle["aggressor_method"] == "unknown"


def test_manual_kimi_packet_and_output_are_evidence_bounded() -> None:
    packet = build_kimi_manual_packet({"symbol": "META", "fact": "reported"})

    assert packet["workflow"] == "manual_kimi_research_v1"
    assert packet["evidence"]["fact"] == "reported"
    assert "output_schema" in packet

    result = validate_kimi_manual_output(synthesis_payload())
    assert result["provider"] == "kimi_manual"
    assert result["order_created"] is False


def test_manual_kimi_output_rejects_invalid_confidence() -> None:
    invalid = synthesis_payload()
    invalid["confidence"] = 1.5

    with pytest.raises(ValidationError):
        validate_kimi_manual_output(invalid)
