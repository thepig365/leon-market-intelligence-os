import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from lmio.config import Settings
from lmio.security import require_admin


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
