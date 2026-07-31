"""Small authentication guard for mutating runtime endpoints."""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException

from lmio.config import get_settings


def require_admin(
    x_lmio_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = get_settings().admin_api_key.get_secret_value()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Mutating API is disabled until LMIO_ADMIN_API_KEY is configured.",
        )
    if not x_lmio_key or not hmac.compare_digest(x_lmio_key, expected):
        raise HTTPException(status_code=401, detail="Invalid LMIO administrator credential.")


def valid_read_credential(value: str | None) -> bool:
    """Validate the server-to-server dashboard credential when configured."""

    expected = get_settings().read_api_key.get_secret_value()
    if not expected:
        return get_settings().environment in {"local", "test"}
    return bool(value and hmac.compare_digest(value, expected))


def valid_cron_credential(value: str | None) -> bool:
    """Validate Vercel's server-side scheduled request credential."""

    expected = get_settings().cron_secret.get_secret_value()
    if not expected or not value or not value.startswith("Bearer "):
        return False
    supplied = value.removeprefix("Bearer ").strip()
    return bool(supplied and hmac.compare_digest(supplied, expected))


def require_cron(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not get_settings().cron_secret.get_secret_value():
        raise HTTPException(
            status_code=503,
            detail="Scheduled refresh is disabled until CRON_SECRET is configured.",
        )
    if not valid_cron_credential(authorization):
        raise HTTPException(status_code=401, detail="Invalid scheduled refresh credential.")
