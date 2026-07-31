import json
from urllib.request import Request

import pytest
from pydantic import ValidationError

from lmio.providers import (
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
