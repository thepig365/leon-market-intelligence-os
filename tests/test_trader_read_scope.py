import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr
from starlette.requests import Request
from starlette.responses import Response

from lmio.main import require_runtime_read_key
from lmio.security import valid_trader_read_credential


@pytest.mark.parametrize(
    "method,path,allowed",
    [
        ("GET", "/api/v1/screens/latest", True),
        ("GET", "/api/v1/options/board", True),
        ("GET", "/api/v1/system-health", True),
        ("POST", "/api/v1/options/board", False),
        ("POST", "/api/v1/operator/full-refresh", False),
        ("POST", "/api/v1/providers/ibkr/options", False),
        ("GET", "/api/v1/reports/history", False),
        ("GET", "/api/v1/options/board/", False),
    ],
)
def test_scoped_key_is_checked_before_all_other_routes(monkeypatch, method, path, allowed):
    monkeypatch.setattr("lmio.main.valid_trader_read_credential", lambda x: x == "trader-test")
    monkeypatch.setattr("lmio.main.valid_read_credential", lambda x: False)
    monkeypatch.setattr("lmio.main.valid_cron_credential", lambda *x: False)
    req = Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [(b"x-lmio-read-key", b"trader-test")],
        }
    )
    next_call = AsyncMock(return_value=Response(status_code=200))
    response = asyncio.run(require_runtime_read_key(req, next_call))
    assert response.status_code == (200 if allowed else 403)
    assert next_call.await_count == int(allowed)


def test_trader_key_disabled_by_default_and_exact_match(monkeypatch):
    settings = SimpleNamespace(trader_read_api_key=SecretStr(""))
    monkeypatch.setattr("lmio.security.get_settings", lambda: settings)
    assert not valid_trader_read_credential("anything")
    settings.trader_read_api_key = SecretStr("test-secret")
    assert valid_trader_read_credential("test-secret")
    assert not valid_trader_read_credential("wrong")
    assert not valid_trader_read_credential(None)
