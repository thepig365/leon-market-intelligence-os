from datetime import UTC, datetime

import httpx

from lmio.supabase_store import SupabaseRuntimeStore


def test_supabase_store_uses_service_role_and_expands_records() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/lmio_schema_versions"):
            return httpx.Response(200, json=[{"version": 6}])
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

    assert store.schema_versions() == [6]
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
