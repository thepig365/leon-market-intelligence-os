"""Small authentication guard for mutating runtime endpoints."""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException

from lmio.config import get_settings
from lmio.telegram import valid_webhook_secret


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
    """Validate private reads, with only explicit local or controlled-test bypasses."""

    settings = get_settings()
    expected = settings.read_api_key.get_secret_value()
    if settings.environment == "test":
        return True
    if settings.environment == "local" and settings.allow_insecure_local_reads:
        return True
    if not expected:
        return False
    return bool(value and hmac.compare_digest(value, expected))


def valid_cron_credential(
    authorization: str | None,
    preview_key: str | None = None,
) -> bool:
    """Validate Vercel Cron or the protected-preview verification header."""

    expected = get_settings().cron_secret.get_secret_value()
    if not expected:
        return False
    if preview_key and hmac.compare_digest(preview_key, expected):
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    supplied = authorization.removeprefix("Bearer ").strip()
    return bool(supplied and hmac.compare_digest(supplied, expected))


def require_cron(
    authorization: Annotated[str | None, Header()] = None,
    x_lmio_cron_key: Annotated[str | None, Header()] = None,
) -> None:
    if not get_settings().cron_secret.get_secret_value():
        raise HTTPException(
            status_code=503,
            detail="Scheduled refresh is disabled until CRON_SECRET is configured.",
        )
    if not valid_cron_credential(authorization, x_lmio_cron_key):
        raise HTTPException(status_code=401, detail="Invalid scheduled refresh credential.")


def require_telegram_webhook(
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = get_settings().telegram_webhook_secret.get_secret_value()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Telegram queries are disabled until the webhook secret is configured.",
        )
    if not valid_webhook_secret(x_telegram_bot_api_secret_token, expected):
        raise HTTPException(status_code=403, detail="Invalid Telegram webhook secret.")
