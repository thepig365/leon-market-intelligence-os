"""Bounded research-worker adapters that cannot control LMIO calculations."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from lmio.providers.base import ProviderHealth, ProviderState
from lmio.providers.contracts import ResearchWorker

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
RESEARCH_PROMPT_VERSION = "lmio-evidence-synthesis-v1"
NEWS_PROMPT_VERSION = "lmio-news-synthesis-v1"
OPTIONS_SCREENSHOT_PROMPT_VERSION = "lmio-options-screenshot-analysis-v1"


class ResearchSynthesis(BaseModel):
    """Strict, evidence-bound output shared by automated and manual workers."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    summary: str
    thesis: str
    supporting_evidence: list[str]
    contrary_evidence: list[str]
    risks: list[str]
    missing_information: list[str]
    source_urls: list[str]
    confidence: float = Field(ge=0, le=1)


OpenAITransport = Callable[[Request, float], dict[str, Any]]


class NewsSynthesis(BaseModel):
    """Strict summary of one minimal, official news-event record."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    trading_focus: str
    investing_focus: str
    missing_information: str
    confidence: float = Field(ge=0, le=1)


class ExtractedOptionAlert(BaseModel):
    """One option-flow alert visibly present in the supplied image."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    expiry: str
    strike: float = Field(ge=0)
    right: str = Field(pattern="^(call|put)$")
    contracts: int = Field(ge=0)
    bought_price: float = Field(ge=0)
    open_interest: int = Field(ge=0)
    total_premium_usd: float = Field(ge=0)
    volume_oi_ratio: float = Field(ge=0)
    extraction_confidence: float = Field(ge=0, le=1)


class OptionTickerAssessment(BaseModel):
    """Conditional research interpretation, never an order instruction."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    flow_bias: str = Field(
        pattern="^(bullish_interest|bearish_interest|mixed|unclear)$"
    )
    why_notable: str
    confirmation_needed: str
    invalidation_or_risk: str
    research_stance: str = Field(pattern="^(watch|wait_for_confirmation|avoid|insufficient_data)$")


class OptionsScreenshotSynthesis(BaseModel):
    """Plain-language, evidence-bounded interpretation of an uploaded screenshot."""

    model_config = ConfigDict(extra="forbid")

    plain_language_summary: str
    alerts: list[ExtractedOptionAlert] = Field(max_length=30)
    notable_patterns: list[str] = Field(max_length=12)
    bullish_clues: list[str] = Field(max_length=10)
    bearish_clues: list[str] = Field(max_length=10)
    what_this_does_not_prove: list[str] = Field(max_length=10)
    confirmation_checks: list[str] = Field(max_length=12)
    ticker_assessments: list[OptionTickerAssessment] = Field(max_length=12)
    overall_confidence: float = Field(ge=0, le=1)


def _default_transport(request: Request, timeout: float) -> dict[str, Any]:
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct:
        return direct
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str) and text:
                    return text
    raise ValueError("OpenAI response contained no output text")


class OpenAIResearchWorker(ResearchWorker):
    """Server-side Responses API adapter, inert until explicitly configured."""

    name = "openai_research"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transport: OpenAITransport = _default_transport,
        timeout: float = 30,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._transport = transport
        self._timeout = timeout

    def health(self) -> ProviderHealth:
        if not self._api_key or not self._model:
            return ProviderHealth(
                provider=self.name,
                state=ProviderState.DISABLED,
                detail="OPENAI_API_KEY and LMIO_OPENAI_MODEL are not both configured",
            )
        return ProviderHealth(
            provider=self.name,
            state=ProviderState.CONFIGURED_NOT_VERIFIED,
            detail="configuration exists but no successful live synthesis is recorded",
        )

    def analyse(self, evidence: dict[str, Any]) -> dict[str, Any]:
        if self.health().state is ProviderState.DISABLED:
            raise RuntimeError("OpenAI research worker is disabled")
        schema = ResearchSynthesis.model_json_schema()
        request_body = {
            "model": self._model,
            "store": False,
            "instructions": (
                "Analyse only the supplied evidence. Do not invent facts, prices, dates, "
                "sources, or conclusions. Explicitly list missing information. This output "
                "is research assistance only and cannot approve a candidate or create an order."
            ),
            "input": json.dumps(
                {
                    "prompt_version": RESEARCH_PROMPT_VERSION,
                    "evidence": evidence,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "lmio_research_synthesis",
                    "description": "Evidence-bound LMIO research synthesis",
                    "schema": schema,
                    "strict": True,
                }
            },
        }
        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        response = self._transport(request, self._timeout)
        result = ResearchSynthesis.model_validate_json(_extract_output_text(response))
        return {
            **result.model_dump(),
            "provider": self.name,
            "model": self._model,
            "prompt_version": RESEARCH_PROMPT_VERSION,
            "order_created": False,
        }


class OpenAINewsWorker:
    """Server-only, tool-free Responses API adapter for official event metadata."""

    name = "openai_news"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transport: OpenAITransport = _default_transport,
        timeout: float = 30,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._transport = transport
        self._timeout = timeout

    def analyse(self, evidence: dict[str, Any]) -> dict[str, Any]:
        if not self._api_key or not self._model:
            raise RuntimeError("OpenAI news worker is disabled")
        request_body = {
            "model": self._model,
            "store": False,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 500,
            "instructions": (
                "用中文分析且只使用提供的官方事件元数据。不得补写数据、方向、价格、"
                "日期或结论。说明交易者与投资者应核对什么；资料不足必须明确指出。"
                "不得给出买卖指令、目标价或自动交易建议。"
            ),
            "input": json.dumps(
                {"prompt_version": NEWS_PROMPT_VERSION, "event": evidence},
                separators=(",", ":"),
                sort_keys=True,
            ),
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "lmio_news_synthesis",
                    "schema": NewsSynthesis.model_json_schema(),
                    "strict": True,
                },
            },
        }
        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        response = self._transport(request, self._timeout)
        result = NewsSynthesis.model_validate_json(_extract_output_text(response))
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        return {
            **result.model_dump(),
            "provider": self.name,
            "model": self._model,
            "prompt_version": NEWS_PROMPT_VERSION,
            "usage": {
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
            },
            "order_created": False,
        }


class OpenAIOptionsScreenshotWorker:
    """Tool-free vision adapter for owner-supplied option-flow screenshots."""

    name = "openai_options_screenshot"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transport: OpenAITransport = _default_transport,
        timeout: float = 60,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._transport = transport
        self._timeout = timeout

    def analyse(self, image_data_url: str) -> dict[str, Any]:
        if not self._api_key or not self._model:
            raise RuntimeError("OpenAI options screenshot worker is disabled")
        request_body = {
            "model": self._model,
            "store": False,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 1_600,
            "instructions": (
                "你是 LMIO 的期权异动截图研究助手。只读取截图内清晰可见的文字与数字，"
                "不得联网、调用工具、补写行情或猜测缺失值。先精确提取合约，再用非技术中文"
                "解释它们可能代表的多空兴趣。必须说明单笔成交不能证明开仓、平仓、机构意图、"
                "组合对冲或未来走势。不要给出直接买入、卖出、目标价、仓位或下单指令；只能给出"
                "观察、等待确认、回避或资料不足，并列出成交方向、次日 OI、标的走势、IV、价差、"
                "新闻与流动性等确认条件。"
            ),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "分析这张期权异动截图。区分截图事实与研究推断，返回规定 JSON。"
                            ),
                        },
                        {"type": "input_image", "image_url": image_data_url, "detail": "high"},
                    ],
                }
            ],
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "lmio_options_screenshot_synthesis",
                    "schema": OptionsScreenshotSynthesis.model_json_schema(),
                    "strict": True,
                },
            },
        }
        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        response = self._transport(request, self._timeout)
        result = OptionsScreenshotSynthesis.model_validate_json(_extract_output_text(response))
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        return {
            **result.model_dump(),
            "provider": self.name,
            "model": self._model,
            "prompt_version": OPTIONS_SCREENSHOT_PROMPT_VERSION,
            "usage": {
                "input_tokens": int(usage.get("input_tokens", 0)),
                "output_tokens": int(usage.get("output_tokens", 0)),
            },
            "order_created": False,
            "execution_allowed": False,
        }


def build_kimi_manual_packet(evidence: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal packet for a human-mediated Kimi research pass."""

    return {
        "workflow": "manual_kimi_research_v1",
        "instructions": (
            "Analyse only the supplied evidence. Return JSON matching output_schema. "
            "Do not invent facts and do not make approval or trading decisions."
        ),
        "evidence": evidence,
        "output_schema": ResearchSynthesis.model_json_schema(),
        "approval_boundary": "Output remains draft until reviewed inside LMIO.",
    }


def validate_kimi_manual_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a manually returned Kimi result before LMIO can display it."""

    result = ResearchSynthesis.model_validate(payload)
    return {
        **result.model_dump(),
        "provider": "kimi_manual",
        "prompt_version": RESEARCH_PROMPT_VERSION,
        "order_created": False,
    }
