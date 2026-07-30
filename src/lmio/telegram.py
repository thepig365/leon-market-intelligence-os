"""Quiet-by-default Telegram delivery with persistence-backed deduplication."""

import hashlib
import json
import sqlite3
from enum import StrEnum
from urllib import parse, request

from lmio.store import RuntimeStore


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
) -> None:
    with store.connection() as connection:
        connection.execute(
            """
            INSERT INTO telegram_deliveries
                (dedupe_key, status, payload, provider_message_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                key,
                status,
                json.dumps(
                    {"message": message, "kind": kind, "error": error},
                    ensure_ascii=False,
                ),
                provider_message_id,
            ),
        )


def message_key(message: str) -> str:
    return hashlib.sha256(message.strip().encode()).hexdigest()


def queue_or_send(
    store: RuntimeStore,
    message: str,
    *,
    bot_token: str = "",
    chat_id: str = "",
    kind: MessageKind = MessageKind.PREMARKET,
    max_per_hour: int = 6,
) -> str:
    """Queue without credentials, or send once when explicit credentials exist."""

    key = message_key(message)
    store.migrate()
    with store.connection() as connection:
        existing = connection.execute(
            "SELECT status FROM telegram_deliveries WHERE dedupe_key = ?", (key,)
        ).fetchone()
        if existing:
            return str(existing["status"])
        sent_last_hour = connection.execute(
            """
            SELECT COUNT(*) FROM telegram_deliveries
            WHERE status = 'sent' AND created_at >= datetime('now', '-1 hour')
            """
        ).fetchone()[0]
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

    status = "queued_not_configured"
    provider_message_id = None
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        body = parse.urlencode({"chat_id": chat_id, "text": message}).encode()
        telegram_request = request.Request(url, data=body, method="POST")
        try:
            with request.urlopen(telegram_request, timeout=10) as response:
                payload = json.loads(response.read())
            if not payload.get("ok"):
                raise RuntimeError("Telegram rejected the delivery")
            provider_message_id = str(payload["result"]["message_id"])
            status = "sent"
        except Exception as error:  # provider failure must not stop the research pipeline
            _persist_delivery(
                store,
                key=key,
                status="failed",
                message=message,
                kind=kind,
                provider_message_id=None,
                error=type(error).__name__,
            )
            return "failed"
    _persist_delivery(
        store,
        key=key,
        status=status,
        message=message,
        kind=kind,
        provider_message_id=provider_message_id,
    )
    return status


def delivery_count(store: RuntimeStore) -> int:
    try:
        return store.counts()["telegram_deliveries"]
    except sqlite3.OperationalError:
        return 0
