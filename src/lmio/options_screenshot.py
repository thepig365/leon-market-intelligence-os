"""Validation for transient option-flow screenshot inputs."""

from __future__ import annotations

import base64
import binascii

MAX_OPTIONS_SCREENSHOT_BYTES = 2_000_000
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}


def validate_options_screenshot_data_url(value: str) -> tuple[str, int]:
    """Return MIME type and byte count without retaining decoded image data."""

    if not value.startswith("data:") or ";base64," not in value:
        raise ValueError("Screenshot must be a base64 data URL.")
    header, encoded = value.split(",", 1)
    mime_type = header.removeprefix("data:").removesuffix(";base64").lower()
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Screenshot must be PNG, JPEG, or WebP.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Screenshot encoding is invalid.") from error
    if not raw or len(raw) > MAX_OPTIONS_SCREENSHOT_BYTES:
        raise ValueError("Screenshot must be between 1 byte and 2 MB.")
    signatures = {
        "image/png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": raw.startswith(b"\xff\xd8\xff"),
        "image/webp": raw.startswith(b"RIFF") and raw[8:12] == b"WEBP",
    }
    if not signatures[mime_type]:
        raise ValueError("Screenshot content does not match its declared image type.")
    return mime_type, len(raw)
