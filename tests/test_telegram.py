from pathlib import Path
from urllib import parse

from lmio.store import RuntimeStore
from lmio.telegram import (
    MAX_MESSAGE_CHARS,
    MessageKind,
    format_message,
    queue_or_send,
)

VALID_TOKEN = "123456789:abcdefghijklmnopqrstuvwxyz_123456"
VALID_CHAT_ID = "-1001234567890"


def test_telegram_is_queued_without_credentials_and_deduplicated(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    assert queue_or_send(store, "中文测试简报") == "queued_not_configured"
    assert queue_or_send(store, "中文测试简报") == "queued_not_configured"
    assert store.counts()["telegram_deliveries"] == 1


def test_non_urgent_telegram_is_suppressed_at_rate_limit(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.migrate()
    with store.connection() as connection:
        for index in range(2):
            connection.execute(
                """
                INSERT INTO telegram_deliveries(dedupe_key, status, payload)
                VALUES (?, 'sent', '{}')
                """,
                (f"prior-{index}",),
            )

    status = queue_or_send(
        store,
        "新盘后简报",
        bot_token=VALID_TOKEN,
        chat_id=VALID_CHAT_ID,
        kind=MessageKind.AFTER_CLOSE,
        max_per_hour=2,
    )

    assert status == "suppressed_rate_limit"


def test_queued_delivery_can_send_after_credentials_are_configured(
    tmp_path: Path,
) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    message = "等待配置后发送"
    calls: list[dict[str, list[str]]] = []

    assert queue_or_send(store, message) == "queued_not_configured"

    def transport(url: str, body: bytes, timeout: float, max_bytes: int) -> bytes:
        assert url.startswith("https://api.telegram.org/bot")
        assert timeout == 10.0
        assert max_bytes > 0
        calls.append(parse.parse_qs(body.decode()))
        return b'{"ok":true,"result":{"message_id":42}}'

    assert (
        queue_or_send(
            store,
            message,
            bot_token=VALID_TOKEN,
            chat_id=VALID_CHAT_ID,
            transport=transport,
        )
        == "sent"
    )
    assert calls == [{"chat_id": [VALID_CHAT_ID], "text": [message]}]
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT status, provider_message_id, attempt_count
            FROM telegram_deliveries
            """
        ).fetchone()
    assert row is not None
    assert dict(row) == {
        "status": "sent",
        "provider_message_id": "42",
        "attempt_count": 1,
    }


def test_failed_delivery_retries_once_per_invocation(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    attempts = 0

    def transport(_url: str, _body: bytes, _timeout: float, _limit: int) -> bytes:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("synthetic timeout")
        return b'{"ok":true,"result":{"message_id":99}}'

    arguments = {
        "bot_token": VALID_TOKEN,
        "chat_id": VALID_CHAT_ID,
        "transport": transport,
    }
    assert queue_or_send(store, "可重试简报", **arguments) == "failed"
    assert queue_or_send(store, "可重试简报", **arguments) == "sent"
    assert attempts == 2
    with store.connection() as connection:
        row = connection.execute(
            "SELECT status, attempt_count, payload FROM telegram_deliveries"
        ).fetchone()
    assert row is not None
    assert row["status"] == "sent"
    assert row["attempt_count"] == 2
    assert "synthetic timeout" not in row["payload"]


def test_delivery_stops_after_bounded_attempts(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    attempts = 0

    def transport(_url: str, _body: bytes, _timeout: float, _limit: int) -> bytes:
        nonlocal attempts
        attempts += 1
        raise ConnectionError("synthetic")

    for _ in range(3):
        assert (
            queue_or_send(
                store,
                "有界重试",
                bot_token=VALID_TOKEN,
                chat_id=VALID_CHAT_ID,
                transport=transport,
            )
            == "failed"
        )
    assert (
        queue_or_send(
            store,
            "有界重试",
            bot_token=VALID_TOKEN,
            chat_id=VALID_CHAT_ID,
            transport=transport,
        )
        == "failed_exhausted"
    )
    assert attempts == 3


def test_invalid_credentials_and_oversized_messages_fail_without_network(
    tmp_path: Path,
) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    called = False

    def transport(_url: str, _body: bytes, _timeout: float, _limit: int) -> bytes:
        nonlocal called
        called = True
        return b"{}"

    assert (
        queue_or_send(
            store,
            "简报",
            bot_token="not-a-token",
            chat_id="not-a-chat",
            transport=transport,
        )
        == "failed_validation"
    )
    assert (
        queue_or_send(
            store,
            "过" * (MAX_MESSAGE_CHARS + 1),
            bot_token=VALID_TOKEN,
            chat_id=VALID_CHAT_ID,
            transport=transport,
        )
        == "failed_validation"
    )
    assert called is False
    with store.connection() as connection:
        payloads = [
            str(row["payload"])
            for row in connection.execute("SELECT payload FROM telegram_deliveries").fetchall()
        ]
    assert all("not-a-token" not in payload for payload in payloads)
    assert all("not-a-chat" not in payload for payload in payloads)


def test_malformed_or_oversized_provider_response_fails_safely(
    tmp_path: Path,
) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")

    def malformed(_url: str, _body: bytes, _timeout: float, _limit: int) -> bytes:
        return b'{"ok":true,"result":{}}'

    assert (
        queue_or_send(
            store,
            "错误响应",
            bot_token=VALID_TOKEN,
            chat_id=VALID_CHAT_ID,
            transport=malformed,
        )
        == "failed"
    )

    def oversized(_url: str, _body: bytes, _timeout: float, limit: int) -> bytes:
        return b"x" * (limit + 1)

    assert (
        queue_or_send(
            store,
            "超大响应",
            bot_token=VALID_TOKEN,
            chat_id=VALID_CHAT_ID,
            transport=oversized,
        )
        == "failed"
    )


def test_all_fixed_report_kinds_have_quiet_chinese_format() -> None:
    for kind in MessageKind:
        message = format_message(
            kind,
            regime="Range",
            opportunities=[],
            risks=["数据待验证"],
            next_actions=["等待确认"],
        )
        assert "不会执行交易" in message
        assert "主要风险" in message
