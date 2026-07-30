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
