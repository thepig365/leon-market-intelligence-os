import base64

import pytest

from lmio.config import Settings
from lmio.options_screenshot import validate_options_screenshot_data_url
from lmio.service import LMIOService


def data_url(mime_type: str, raw: bytes) -> str:
    return f"data:{mime_type};base64,{base64.b64encode(raw).decode()}"


@pytest.mark.parametrize(
    ("mime_type", "raw"),
    [
        ("image/png", b"\x89PNG\r\n\x1a\ncontent"),
        ("image/jpeg", b"\xff\xd8\xffcontent"),
        ("image/webp", b"RIFF0000WEBPcontent"),
    ],
)
def test_options_screenshot_accepts_only_matching_image_content(mime_type: str, raw: bytes) -> None:
    assert validate_options_screenshot_data_url(data_url(mime_type, raw)) == (
        mime_type,
        len(raw),
    )


def test_options_screenshot_rejects_spoofed_content() -> None:
    with pytest.raises(ValueError, match="does not match"):
        validate_options_screenshot_data_url(data_url("image/png", b"not-an-image"))


def test_options_screenshot_rejects_oversized_content() -> None:
    with pytest.raises(ValueError, match="2 MB"):
        validate_options_screenshot_data_url(
            data_url("image/png", b"\x89PNG\r\n\x1a\n" + b"x" * 2_000_000)
        )


def test_service_persists_only_structured_analysis_and_reserves_cap(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeWorker:
        name = "openai_options_screenshot"

        def __init__(self, **kwargs) -> None:
            pass

        def analyse(self, image_data_url: str) -> dict[str, object]:
            assert image_data_url.startswith("data:image/png;base64,")
            return {
                "plain_language_summary": "等待标的走势与次日 OI 确认。",
                "alerts": [],
                "notable_patterns": [],
                "bullish_clues": [],
                "bearish_clues": [],
                "what_this_does_not_prove": ["不能证明开仓方向。"],
                "confirmation_checks": ["核对次日 OI。"],
                "ticker_assessments": [],
                "overall_confidence": 0.5,
                "provider": self.name,
                "model": "gpt-5.6-luna",
                "prompt_version": "test",
                "usage": {"input_tokens": 100, "output_tokens": 50},
                "order_created": False,
                "execution_allowed": False,
            }

    monkeypatch.setattr("lmio.service.OpenAIOptionsScreenshotWorker", FakeWorker)
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "runtime.sqlite3",
        openai_api_key="server-secret",
        openai_monthly_cap_usd=5,
    )
    service = LMIOService(settings)
    image = data_url("image/png", b"\x89PNG\r\n\x1a\ncontent")
    result = service.analyse_options_screenshot(
        image,
        mime_type="image/png",
        image_bytes=15,
        actor_role="owner",
    )

    assert result["image_retained"] is False
    assert result["order_created"] is False
    stored = service.store.history_json("options_flow", 1)[0]
    assert stored["payload"]["input"]["image_retained"] is False
    assert image not in str(stored)
    usage = service.store.history_json("ai_usage", 1)[0]
    assert usage["cost_usd"] == pytest.approx(0.05)
