"""Quiet-by-default Telegram delivery with persistence-backed deduplication."""

import hashlib
import json
import re
import sqlite3
from collections.abc import Callable
from enum import StrEnum
from urllib import parse, request

from lmio.store import RuntimeStore

MAX_MESSAGE_CHARS = 4096
MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_MAX_ATTEMPTS = 3
BOT_TOKEN_PATTERN = re.compile(r"^[1-9]\d{5,14}:[A-Za-z0-9_-]{20,}$")
CHAT_ID_PATTERN = re.compile(r"^(?:-?\d{1,24}|@[A-Za-z][A-Za-z0-9_]{4,31})$")
TelegramTransport = Callable[[str, bytes, float, int], bytes]


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
    store: RuntimeStore,
    *,
    key: str,
    status: str,
    message: str,
    kind: MessageKind,
    provider_message_id: str | None,
    error: str | None = None,
    attempt_increment: int = 0,
) -> None:
    with store.connection() as connection:
        connection.execute(
            """
            INSERT INTO telegram_deliveries
                (
                    dedupe_key,
                    status,
                    payload,
                    provider_message_id,
                    attempt_count,
                    last_attempt_at
                )
            VALUES (
                ?, ?, ?, ?, ?,
                CASE WHEN ? > 0 THEN CURRENT_TIMESTAMP ELSE NULL END
            )
            ON CONFLICT(dedupe_key) DO UPDATE SET
                status = excluded.status,
                payload = excluded.payload,
                provider_message_id = excluded.provider_message_id,
                attempt_count = (
                    telegram_deliveries.attempt_count + excluded.attempt_count
                ),
                last_attempt_at = CASE
                    WHEN excluded.attempt_count > 0 THEN CURRENT_TIMESTAMP
                    ELSE telegram_deliveries.last_attempt_at
                END
            """,
            (
                key,
                status,
                json.dumps(
                    {"message": message, "kind": kind, "error": error},
                    ensure_ascii=False,
                ),
                provider_message_id,
                attempt_increment,
                attempt_increment,
            ),
        )


def message_key(message: str) -> str:
    return hashlib.sha256(message.strip().encode()).hexdigest()


def _default_transport(url: str, body: bytes, timeout: float, max_bytes: int) -> bytes:
    telegram_request = request.Request(url, data=body, method="POST")
    with request.urlopen(telegram_request, timeout=timeout) as response:
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("Telegram response exceeded the size limit")
    return payload


def _valid_credentials(bot_token: str, chat_id: str) -> bool:
    return bool(BOT_TOKEN_PATTERN.fullmatch(bot_token) and CHAT_ID_PATTERN.fullmatch(chat_id))


def queue_or_send(
    store: RuntimeStore,
    message: str,
    *,
    bot_token: str = "",
    chat_id: str = "",
    kind: MessageKind = MessageKind.PREMARKET,
    max_per_hour: int = 6,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    transport: TelegramTransport | None = None,
) -> str:
    """Queue safely, or make one bounded delivery attempt per invocation."""

    key = message_key(message)
    store.migrate()
    with store.connection() as connection:
        existing = connection.execute(
            """
            SELECT status, attempt_count
            FROM telegram_deliveries
            WHERE dedupe_key = ?
            """,
            (key,),
        ).fetchone()
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
        sent_last_hour = connection.execute(
            """
            SELECT COUNT(*) FROM telegram_deliveries
            WHERE status = 'sent' AND created_at >= datetime('now', '-1 hour')
            """
        ).fetchone()[0]

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


def delivery_count(store: RuntimeStore) -> int:
    try:
        return store.counts()["telegram_deliveries"]
    except sqlite3.OperationalError:
        return 0
