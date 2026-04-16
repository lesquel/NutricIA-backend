"""Simple in-memory rate limiter for auth endpoints."""

import time
from collections import defaultdict

# Map: key → last_request_timestamp
_rate_store: dict[str, float] = defaultdict(float)

# Window in seconds
_WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> bool:
    """Return True if the key is allowed (not rate-limited).

    Allows 1 request per window per key. On first call or after window
    expires: allows and records. Within window: denies.
    """
    now = time.monotonic()
    last = _rate_store.get(key, 0.0)
    if now - last < _WINDOW_SECONDS:
        return False  # Rate limited
    _rate_store[key] = now
    return True


def reset_rate_limit(key: str) -> None:
    """Reset the rate limit for a key (for testing)."""
    _rate_store.pop(key, None)
