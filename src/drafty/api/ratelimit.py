"""Per-IP rate limiting and the global daily token cap.

Raises :class:`RateLimitExceeded`, which the API turns into a friendly 429.
"""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimitExceeded(Exception):
    """Raised when an IP or the daily cap blocks a new run."""


class RateLimiter:
    """Sliding one-hour window per IP plus a global daily token cap check."""

    def __init__(self, per_hour: int = 20, daily_token_cap: int | None = None) -> None:
        self.per_hour = per_hour
        self.daily_token_cap = daily_token_cap
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, ip: str, daily_used: int = 0) -> None:
        """Record a start attempt for ``ip`` or raise :class:`RateLimitExceeded`."""
        if self.daily_token_cap is not None and daily_used >= self.daily_token_cap:
            raise RateLimitExceeded("demo limit reached, try again tomorrow")

        now = time.monotonic()
        recent = [hit for hit in self._hits[ip] if now - hit < 3600.0]
        if len(recent) >= self.per_hour:
            self._hits[ip] = recent
            raise RateLimitExceeded("too many runs started from this address; try again later")
        recent.append(now)
        self._hits[ip] = recent
