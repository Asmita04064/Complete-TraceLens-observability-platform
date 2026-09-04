"""Small field-based redaction layer for trace payloads."""

SENSITIVE_KEYS = {
    "password", "passwd", "secret", "api_key", "apikey", "access_token",
    "refresh_token", "authorization", "bearer", "credential",
}


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
    return value
