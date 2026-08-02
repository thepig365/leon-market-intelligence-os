from datetime import UTC, datetime
from pathlib import Path

import httpx

from lmio.supabase_store import SupabaseRuntimeStore


def test_supabase_store_uses_service_role_and_expands_records() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/lmio_schema_versions"):
            return httpx.Response(200, json=[{"version": 8}])
        if request.url.path.endswith("/lmio_records") and request.method == "POST":
            return httpx.Response(201, json=[{"id": 41}])
        if request.url.path.endswith("/lmio_records"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 41,
                        "symbol": "SNDK",
                        "provider": "finviz",
                        "state": "ready",
                        "payload": {"score": 82},
                        "input_payload": None,
                        "result_payload": None,
                        "metadata": {"calculation_version": "screens-v1"},
                        "created_at": "2026-07-31T00:00:00+00:00",
                    }
                ],
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    store = SupabaseRuntimeStore(
        "https://example.supabase.co",
        "service-secret",
        transport=httpx.MockTransport(handler),
    )

    assert store.schema_versions() == [8]
    assert (
        store.append_json(
            "screen_runs",
            {
                "symbol": "SNDK",
                "provider": "finviz",
                "state": "ready",
                "payload": {"score": 82},
            },
        )
        == 41
    )
    assert store.history_json("screen_runs")[0]["calculation_version"] == "screens-v1"
    assert all(request.headers["apikey"] == "service-secret" for request in requests)
    assert all(request.headers["authorization"] == "Bearer service-secret" for request in requests)


def test_supabase_synthetic_records_use_a_physically_separate_table() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path.endswith("/lmio_synthetic_records")
        if request.method == "POST":
            return httpx.Response(201, json=[{"id": 9}])
        return httpx.Response(
            200,
            json=[
                {
                    "id": 9,
                    "record_type": "daily_run",
                    "provenance": "synthetic_replay",
                    "payload": {"watermark": "demo"},
                    "created_at": "2026-08-02T00:00:00Z",
                }
            ],
        )

    store = SupabaseRuntimeStore(
        "https://example.supabase.co",
        "service-secret",
        transport=httpx.MockTransport(handler),
    )

    assert (
        store.append_json(
            "synthetic_records",
            {
                "record_type": "daily_run",
                "provenance": "synthetic_replay",
                "payload": {"watermark": "demo"},
            },
        )
        == 9
    )
    assert store.history_json("synthetic_records")[0]["provenance"] == "synthetic_replay"
    assert all("lmio_records" not in request.url.path for request in requests)


def test_supabase_telegram_count_uses_exact_server_count() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/lmio_telegram_deliveries")
        assert request.url.params["status"] == "eq.sent"
        return httpx.Response(200, json=[], headers={"content-range": "0-2/3"})

    store = SupabaseRuntimeStore(
        "https://example.supabase.co",
        "service-secret",
        transport=httpx.MockTransport(handler),
    )

    assert store.sent_telegram_count_since(datetime(2026, 7, 31, tzinfo=UTC)) == 3


def test_supabase_provider_snapshot_uses_atomic_rpc() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/rpc/lmio_put_provider_snapshot")
        payload = __import__("json").loads(request.content)
        assert payload["p_symbol"] == "SNDK"
        return httpx.Response(200, json=True)

    store = SupabaseRuntimeStore(
        "https://example.supabase.co",
        "service-secret",
        transport=httpx.MockTransport(handler),
    )

    assert store.put_provider_snapshot(
        "fingerprint",
        provider="finviz",
        symbol="SNDK",
        company="SanDisk",
        observed_at="2026-07-31T00:00:00Z",
        payload={"price": 42},
    )


def test_supabase_logical_export_and_restore_rehearsal(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/lmio_schema_versions"):
            return httpx.Response(200, json=[{"version": 8}])
        return httpx.Response(200, json=[])

    store = SupabaseRuntimeStore(
        "https://example.supabase.co",
        "service-secret",
        transport=httpx.MockTransport(handler),
    )
    export = tmp_path / "export"
    manifest = store.backup_export(export)
    rehearsal = store.restore_rehearsal(export, tmp_path / "restore.sqlite3")

    assert manifest["schema_versions"] == [8]
    assert all(item["sha256"] for item in manifest["files"].values())
    assert rehearsal["status"] == "passed"
    assert "point-in-time" in manifest["limitations"][0]


def test_supabase_diagnostics_keep_checks_separate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/lmio_schema_versions"):
            return httpx.Response(200, json=[{"version": 8}])
        if request.url.path.endswith("/rpc/lmio_rls_check"):
            return httpx.Response(
                200,
                json={"status": "ok", "tables_checked": 7, "rls_enabled": 7},
            )
        raise AssertionError(request.url)

    store = SupabaseRuntimeStore(
        "https://example.supabase.co",
        "service-secret",
        transport=httpx.MockTransport(handler),
    )

    assert store.connectivity_check()["status"] == "ok"
    assert store.schema_check()["required_version"] == 9
    assert store.schema_check()["status"] == "failed"
    assert store.rls_check()["rls_enabled"] == 7
    assert store.referential_integrity_check()["status"] == "not_applicable"
