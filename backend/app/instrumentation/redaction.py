"""Small field-based redaction layer for trace payloads."""

import re

SENSITIVE_KEYS = {
    "password", "passwd", "secret", "api_key", "apikey", "access_token",
    "refresh_token", "authorization", "bearer", "credential",
}
SENSITIVE_TEXT = re.compile(
    r"(?i)(api[_-]?key|password|passwd|secret|authorization|bearer|token|credential)"
    r"\s*[:=]\s*[^\s,;}]+"
)


def redact(value):
    """Return JSON-like data with credential-shaped fields replaced."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SENSITIVE_TEXT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value
