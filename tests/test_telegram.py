from pathlib import Path

from lmio.store import RuntimeStore
from lmio.telegram import MessageKind, format_message, queue_or_send


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
        bot_token="configured",
        chat_id="configured",
        kind=MessageKind.AFTER_CLOSE,
        max_per_hour=2,
    )

    assert status == "suppressed_rate_limit"


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
