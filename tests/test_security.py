import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import SecretStr

from lmio.config import Settings
from lmio.main import app
from lmio.security import require_admin, require_cron, valid_cron_credential


def test_admin_api_is_disabled_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lmio.security.get_settings",
        lambda: Settings(_env_file=None),
    )

    with pytest.raises(HTTPException) as result:
        require_admin(None)

    assert result.value.status_code == 503


def test_admin_api_uses_constant_time_key_check(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lmio.security.get_settings",
        lambda: Settings(_env_file=None, admin_api_key=SecretStr("approved-test-key")),
    )

    require_admin("approved-test-key")
    with pytest.raises(HTTPException) as result:
        require_admin("wrong")
    assert result.value.status_code == 401


def test_cron_api_requires_bearer_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lmio.security.get_settings",
        lambda: Settings(_env_file=None, cron_secret=SecretStr("scheduled-test-key")),
    )

    assert valid_cron_credential("Bearer scheduled-test-key") is True
    assert valid_cron_credential(None, "scheduled-test-key") is True
    assert valid_cron_credential("scheduled-test-key") is False
    require_cron("Bearer scheduled-test-key")
    require_cron(None, "scheduled-test-key")
    with pytest.raises(HTTPException) as result:
        require_cron("Bearer wrong")
    assert result.value.status_code == 401


def test_every_mutating_route_is_admin_protected() -> None:
    mutating_methods = {"POST", "PUT", "PATCH", "DELETE"}

    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.methods.intersection(mutating_methods):
            continue
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        assert require_admin in dependencies, f"{route.path} is missing require_admin"
