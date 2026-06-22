"""Minimal in-memory rate limiter for auth endpoints.

This is intentionally simple for a capstone deployment: a single-process
sliding-window counter keyed by client IP. It resets on process restart and
does not coordinate across multiple workers/instances. A production system
would back this with Redis (e.g. `INCR` + `EXPIRE`) instead.
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_hits: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _client_key(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit_auth(request: Request) -> None:
    settings = get_settings()
    max_attempts = settings.auth_rate_limit_max_attempts
    window_seconds = settings.auth_rate_limit_window_seconds

    key = _client_key(request)
    now = time.monotonic()
    cutoff = now - window_seconds

    with _lock:
        attempts = [t for t in _hits[key] if t > cutoff]
        if len(attempts) >= max_attempts:
            _hits[key] = attempts
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )
        attempts.append(now)
        _hits[key] = attempts
