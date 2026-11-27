"""Lightweight sliding-window per-IP rate limiter for public API endpoints."""

from __future__ import annotations

import math
import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

from app.core.config import Settings


class RateLimiter:
    """In-memory sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, client_key: str) -> tuple[bool, int]:
        """Record a request if under quota; return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self._window_seconds

        with self._lock:
            bucket = self._buckets.setdefault(client_key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._max_requests:
                retry_after = max(1, math.ceil(bucket[0] + self._window_seconds - now))
                return False, retry_after

            bucket.append(now)
            return True, 0


def extract_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or connection peer."""
    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        first_ip = forwarded.split(",", 1)[0].strip()
        if first_ip:
            return first_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request, limiter: RateLimiter, settings: Settings) -> None:
    """Enforce rate limiting in non-test environments, raising HTTP 429 when exceeded."""
    if settings.environment.lower() == "test":
        return

    client_ip = extract_client_ip(request)
    allowed, retry_after = limiter.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
