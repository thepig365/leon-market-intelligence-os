"""Bounded research-worker adapters that cannot control LMIO calculations."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from lmio.providers.base import ProviderHealth, ProviderState
from lmio.providers.contracts import ResearchWorker

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
RESEARCH_PROMPT_VERSION = "lmio-evidence-synthesis-v1"
NEWS_PROMPT_VERSION = "lmio-news-synthesis-v1"
OPTIONS_SCREENSHOT_PROMPT_VERSION = "lmio-options-screenshot-analysis-v3"


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
    trade_date: str | None
    trade_time: str | None
    expiry: str
    days_to_expiry: int | None
    strike: float = Field(ge=0)
    right: str = Field(pattern="^(call|put)$")
    contracts: int = Field(ge=0)
    trade_price: float = Field(ge=0)
    bid_price: float | None = Field(ge=0)
    ask_price: float | None = Field(ge=0)
    source_action_label: str = Field(pattern="^(bought|sold|none)$")
    aggressor_side: str = Field(pattern="^(buy|sell|unknown)$")
    aggressor_method: str = Field(pattern="^(explicit_label|quote_position|unknown)$")
    aggressor_basis: str
    open_interest: int = Field(ge=0)
    total_premium_usd: float = Field(ge=0)
    volume_oi_ratio: float = Field(ge=0)
    extraction_confidence: float = Field(ge=0, le=1)


class OptionTickerAssessment(BaseModel):
    """Conditional research interpretation, never an order instruction."""

    model_config = ConfigDict(extra="forbid")

    symbol: str
    flow_bias: str = Field(pattern="^(bullish_interest|bearish_interest|mixed|unclear)$")
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
        today: Callable[[], date] = date.today,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip()
        self._transport = transport
        self._timeout = timeout
        self._today = today

    def analyse(self, image_data_url: str) -> dict[str, Any]:
        if not self._api_key or not self._model:
            raise RuntimeError("OpenAI options screenshot worker is disabled")
        today = self._today()
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
                "新闻与流动性等确认条件。expiry 必须输出 ISO 日期 YYYY-MM-DD。"
                "trade_date 只在截图清楚显示该成交所属日期时输出 ISO 日期 YYYY-MM-DD；"
                "trade_time 只记录截图清楚显示的消息或成交时间，否则两者输出 null。"
                "若同一日期标题覆盖多条消息，可把该明确日期应用到标题下的每条成交。"
                "系统会在用户消息提供 analysis_date；截图只显示月日时，"
                "仅当月日与 analysis_date 完全一致，"
                "才可使用 analysis_date 的年份补全，否则年份不清楚时不得猜测。"
                "trade_price 只记录截图成交价；bid_price 和 ask_price 只在截图明确显示"
                "对应报价时记录，否则 null。"
                "若截图明确写 BOUGHT，source_action_label 输出 bought；若明确写 SOLD，输出 sold；"
                "没有明确字样则输出 none。aggressor_side、aggressor_method 和 aggressor_basis "
                "可先按可见证据输出，"
                "但 LMIO 会按明确标签或 Bid/Ask 位置重新核定。不得根据 CALL、PUT 本身猜测主动方向。"
                "days_to_expiry 先输出 null，由 LMIO 优先按截图交易日期、否则按分析日期计算。"
            ),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "分析这张期权异动截图。区分截图事实与研究推断，返回规定 JSON。"
                                f"analysis_date 为 {today.isoformat()}。"
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
        for alert in result.alerts:
            reference_date = today
            if alert.trade_date:
                try:
                    reference_date = date.fromisoformat(alert.trade_date)
                except ValueError:
                    alert.trade_date = None
            try:
                alert.days_to_expiry = (date.fromisoformat(alert.expiry) - reference_date).days
            except ValueError:
                alert.days_to_expiry = None

            if alert.source_action_label == "bought":
                alert.aggressor_side = "buy"
                alert.aggressor_method = "explicit_label"
                alert.aggressor_basis = "截图明确标注 BOUGHT；按来源文字记录为主动买入。"
            elif alert.source_action_label == "sold":
                alert.aggressor_side = "sell"
                alert.aggressor_method = "explicit_label"
                alert.aggressor_basis = "截图明确标注 SOLD；按来源文字记录为主动卖出。"
            elif (
                alert.bid_price is not None
                and alert.ask_price is not None
                and alert.ask_price >= alert.bid_price
                and alert.trade_price >= alert.ask_price
            ):
                alert.aggressor_side = "buy"
                alert.aggressor_method = "quote_position"
                alert.aggressor_basis = (
                    f"截图成交价 ${alert.trade_price:g} 达到或高于 Ask ${alert.ask_price:g}；"
                    "推定为买方主动，但报价与成交时点未必完全同步。"
                )
            elif (
                alert.bid_price is not None
                and alert.ask_price is not None
                and alert.ask_price >= alert.bid_price
                and alert.trade_price <= alert.bid_price
            ):
                alert.aggressor_side = "sell"
                alert.aggressor_method = "quote_position"
                alert.aggressor_basis = (
                    f"截图成交价 ${alert.trade_price:g} 达到或低于 Bid ${alert.bid_price:g}；"
                    "推定为卖方主动，但报价与成交时点未必完全同步。"
                )
            else:
                alert.aggressor_side = "unknown"
                alert.aggressor_method = "unknown"
                alert.aggressor_basis = (
                    "截图没有明确 BOUGHT/SOLD，或成交价位于 Bid/Ask 之间，无法可靠确认主动方向。"
                )
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
