"""Minimal structured audit logging with defensive redaction."""

import json
import logging
import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_KEY_PATTERN = re.compile(
    r"(api[_-]?key|authorization|cookie|credential|password|secret|token)",
    re.IGNORECASE,
)
REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Recursively remove common secret-bearing fields from structured data."""

    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if SENSITIVE_KEY_PATTERN.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    return value


def audit_event(event: str, **fields: Any) -> None:
    """Emit one JSON audit event without accepting raw conversation content."""

    payload = {"event": event, **redact(fields)}
    logging.getLogger("lmio.audit").info(json.dumps(payload, sort_keys=True))
