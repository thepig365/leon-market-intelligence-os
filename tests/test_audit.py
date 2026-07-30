from lmio.audit import REDACTED, redact


def test_redact_removes_nested_secret_fields() -> None:
    payload = {
        "provider": "synthetic",
        "api_key": "not-a-real-secret",
        "nested": {
            "Authorization": "Bearer synthetic",
            "status": "disabled",
        },
        "items": [{"refresh_token": "synthetic"}, {"value": 1}],
    }

    assert redact(payload) == {
        "provider": "synthetic",
        "api_key": REDACTED,
        "nested": {
            "Authorization": REDACTED,
            "status": "disabled",
        },
        "items": [{"refresh_token": REDACTED}, {"value": 1}],
    }
