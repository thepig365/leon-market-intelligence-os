"""Quiet-by-default Telegram delivery with persistence-backed deduplication."""

import hashlib
import json
import sqlite3
from urllib import parse, request

from lmio.store import RuntimeStore


def message_key(message: str) -> str:
    return hashlib.sha256(message.strip().encode()).hexdigest()


def queue_or_send(
    store: RuntimeStore,
    message: str,
    *,
    bot_token: str = "",
    chat_id: str = "",
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

    status = "queued_not_configured"
    provider_message_id = None
    if bot_token and chat_id:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        body = parse.urlencode({"chat_id": chat_id, "text": message}).encode()
        telegram_request = request.Request(url, data=body, method="POST")
        with request.urlopen(telegram_request, timeout=10) as response:
            payload = json.loads(response.read())
        if not payload.get("ok"):
            raise RuntimeError("Telegram rejected the delivery")
        provider_message_id = str(payload["result"]["message_id"])
        status = "sent"
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
                json.dumps({"message": message}, ensure_ascii=False),
                provider_message_id,
            ),
        )
    return status


def delivery_count(store: RuntimeStore) -> int:
    try:
        return store.counts()["telegram_deliveries"]
    except sqlite3.OperationalError:
        return 0
