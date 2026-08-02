"""Quiet-by-default Telegram delivery with persistence-backed deduplication."""

import hashlib
import hmac
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from urllib import parse, request

import httpx

from lmio.domain import SecuritySnapshot
from lmio.screens import strategies_for
from lmio.store import RuntimeStore
from lmio.supabase_store import SupabaseRuntimeStore

MAX_MESSAGE_CHARS = 4096
MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_MAX_ATTEMPTS = 3
BOT_TOKEN_PATTERN = re.compile(r"^[1-9]\d{5,14}:[A-Za-z0-9_-]{20,}$")
CHAT_ID_PATTERN = re.compile(r"^(?:-?\d{1,24}|@[A-Za-z][A-Za-z0-9_]{4,31})$")
SYMBOL_QUERY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9.-]{0,9}$")
TelegramTransport = Callable[[str, bytes, float, int], bytes]
TelegramStore = RuntimeStore | SupabaseRuntimeStore


class MessageKind(StrEnum):
    PREMARKET = "premarket"
    AFTER_OPEN = "after_open"
    AFTER_CLOSE = "after_close"
    WEEKEND = "weekend"
    IMMEDIATE_ALERT = "immediate_alert"


REPORT_TITLES = {
    MessageKind.PREMARKET: "LMIO 盘前简报",
    MessageKind.AFTER_OPEN: "LMIO 开盘后观察",
    MessageKind.AFTER_CLOSE: "LMIO 收盘复盘",
    MessageKind.WEEKEND: "LMIO 周末策略复盘",
    MessageKind.IMMEDIATE_ALERT: "LMIO 重要事件提醒",
}


def format_message(
    kind: MessageKind,
    *,
    regime: str,
    opportunities: list[str],
    risks: list[str],
    next_actions: list[str],
) -> str:
    def lines(items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "- 无"

    return "\n".join(
        (
            REPORT_TITLES[kind],
            f"市场状态：{regime}",
            "重点机会：",
            lines(opportunities),
            "主要风险：",
            lines(risks),
            "下一步确认：",
            lines(next_actions),
            "仅供研究与决策支持；不会执行交易。",
        )
    )


def _persist_delivery(
    store: TelegramStore,
    *,
    key: str,
    status: str,
    message: str,
    kind: MessageKind,
    provider_message_id: str | None,
    error: str | None = None,
    attempt_increment: int = 0,
) -> None:
    store.upsert_telegram_delivery(
        key=key,
        status=status,
        payload={"message": message, "kind": kind, "error": error},
        provider_message_id=provider_message_id,
        attempt_increment=attempt_increment,
    )


def message_key(message: str, context: str = "") -> str:
    material = f"{context.strip()}|{message.strip()}"
    return hashlib.sha256(material.encode()).hexdigest()


def _default_transport(url: str, body: bytes, timeout: float, max_bytes: int) -> bytes:
    telegram_request = request.Request(url, data=body, method="POST")
    with request.urlopen(telegram_request, timeout=timeout) as response:
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("Telegram response exceeded the size limit")
    return payload


def _valid_credentials(bot_token: str, chat_id: str) -> bool:
    return bool(BOT_TOKEN_PATTERN.fullmatch(bot_token) and CHAT_ID_PATTERN.fullmatch(chat_id))


def valid_webhook_secret(provided: str | None, expected: str) -> bool:
    """Compare Telegram's webhook secret without leaking timing information."""

    return bool(provided and expected and hmac.compare_digest(provided, expected))


def parse_symbol_query(text: str) -> str | None:
    """Accept a plain ticker or `/quote TICKER` and reject all other input."""

    normalised = text.strip()
    if normalised.lower().startswith("/quote "):
        normalised = normalised.split(maxsplit=1)[1].strip()
    if not SYMBOL_QUERY_PATTERN.fullmatch(normalised):
        return None
    return normalised.upper()


def format_symbol_snapshot(snapshot: SecuritySnapshot) -> str:
    """Render one concise, human-readable Finviz response for Leon."""

    def optional_number(label: str, value: float | None, suffix: str = "") -> str:
        return f"{label}：{value:.2f}{suffix}" if value is not None else f"{label}：暂无数据"

    strategy_names = {
        "quality_growth_momentum": "质量增长动量",
        "earnings_revision_momentum": "盈利预期动量",
        "institutional_accumulation": "机构累积",
        "activist_catalyst": "积极股东催化",
        "insider_value": "内部人价值",
        "quality_at_reasonable_price": "合理价格质量",
        "post_earnings_announcement_drift": "财报后延续",
        "news_driven": "新闻驱动",
        "oversold_reversal": "超卖反转",
        "short_squeeze": "空头挤压",
        "pattern_recognition": "图形识别",
    }
    matched = [
        strategy_names.get(strategy.value, strategy.value) for strategy in strategies_for(snapshot)
    ]
    observed = snapshot.observed_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return "\n".join(
        (
            f"LMIO · {snapshot.symbol} Finviz 快照",
            f"公司：{snapshot.company}",
            f"价格：US${snapshot.price:.2f}",
            f"市值：US${snapshot.market_cap_m / 1000:.2f}B",
            optional_number("相对成交量", snapshot.relative_volume),
            optional_number("6个月相对强度", snapshot.relative_strength_6m, "%"),
            optional_number("RSI(14)", snapshot.rsi_14),
            f"图形：{snapshot.chart_pattern or 'Finviz 暂无图形标记'}",
            f"匹配策略：{'、'.join(matched) if matched else '当前未通过已批准筛选条件'}",
            f"数据时间：{observed}",
            "来源：Finviz Elite API",
            "仅供研究与决策支持；不会执行交易。",
        )
    )


def queue_or_send(
    store: TelegramStore,
    message: str,
    *,
    bot_token: str = "",
    chat_id: str = "",
    kind: MessageKind = MessageKind.PREMARKET,
    max_per_hour: int = 6,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    transport: TelegramTransport | None = None,
    dedupe_context: str = "",
) -> str:
    """Queue safely, or make one bounded delivery attempt per invocation."""

    key = message_key(message, dedupe_context)
    store.migrate()
    existing = store.telegram_delivery(key)
    if existing and existing["status"] == "sent":
        return str(existing["status"])
    attempt_count = int(existing["attempt_count"]) if existing else 0
    if attempt_count >= max_attempts:
        _persist_delivery(
            store,
            key=key,
            status="failed_exhausted",
            message=message,
            kind=kind,
            provider_message_id=None,
            error="MaxAttemptsExceeded",
        )
        return "failed_exhausted"
    sent_last_hour = store.sent_telegram_count_since(datetime.now(UTC) - timedelta(hours=1))

    if not message.strip() or len(message) > MAX_MESSAGE_CHARS:
        _persist_delivery(
            store,
            key=key,
            status="failed_validation",
            message=message,
            kind=kind,
            provider_message_id=None,
            error="MessageValidationError",
        )
        return "failed_validation"

    credentials_present = bool(bot_token or chat_id)
    if not credentials_present:
        _persist_delivery(
            store,
            key=key,
            status="queued_not_configured",
            message=message,
            kind=kind,
            provider_message_id=None,
        )
        return "queued_not_configured"
    if not _valid_credentials(bot_token, chat_id):
        _persist_delivery(
            store,
            key=key,
            status="failed_validation",
            message=message,
            kind=kind,
            provider_message_id=None,
            error="CredentialValidationError",
        )
        return "failed_validation"

    if sent_last_hour >= max_per_hour and kind is not MessageKind.IMMEDIATE_ALERT:
        _persist_delivery(
            store,
            key=key,
            status="suppressed_rate_limit",
            message=message,
            kind=kind,
            provider_message_id=None,
        )
        return "suppressed_rate_limit"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    send = transport or _default_transport
    try:
        raw_payload = send(url, body, 10.0, MAX_RESPONSE_BYTES)
        if len(raw_payload) > MAX_RESPONSE_BYTES:
            raise ValueError("Telegram response exceeded the size limit")
        payload = json.loads(raw_payload)
        result = payload.get("result") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or payload.get("ok") is not True
            or not isinstance(result, dict)
            or "message_id" not in result
        ):
            raise RuntimeError("Telegram returned an invalid delivery response")
        provider_message_id = str(result["message_id"])
    except Exception as error:  # provider failure must not stop the research pipeline
        _persist_delivery(
            store,
            key=key,
            status="failed",
            message=message,
            kind=kind,
            provider_message_id=None,
            error=type(error).__name__,
            attempt_increment=1,
        )
        return "failed"

    _persist_delivery(
        store,
        key=key,
        status="sent",
        message=message,
        kind=kind,
        provider_message_id=provider_message_id,
        attempt_increment=1,
    )
    return "sent"


def delivery_count(store: TelegramStore) -> int:
    try:
        return store.counts()["telegram_deliveries"]
    except (RuntimeError, httpx.HTTPError):
        return 0
