"""A small per-user rate limit for the chatbot endpoint.

Deliberately in-process and dependency-free. This is a single-process capstone
application, and a distributed limiter (Redis, flask-limiter) would add
infrastructure the project does not otherwise have for a problem it does not
otherwise have. The trade-off is stated plainly: with several worker processes
each would keep its own counter, so the effective limit multiplies by the
worker count.

Two properties matter more than sophistication here:

* The key is the authenticated user id the server resolved, never anything the
  client sent. A caller cannot pick their own bucket.
* Only a window start and a count are kept. No question, no answer, no IP, and
  nothing is written to the database.

``now`` is injectable so tests are deterministic rather than sleep-based.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


APP_EXTENSION_KEY = "chatbot_rate_limit"


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of one check."""

    allowed: bool
    remaining: int
    retry_after: int

    @property
    def limited(self) -> bool:
        return not self.allowed


class FixedWindowRateLimiter:
    """Fixed-window counter per user.

    A fixed window can allow up to 2x the limit across a window boundary. That
    is acceptable for protecting a paid API from accidental hammering, and it
    keeps the state to two numbers per user with no background cleanup.
    """

    # Prune only once the map is big enough to be worth walking; a handful of
    # stale entries costs less than sweeping on every request.
    PRUNE_THRESHOLD = 1024

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = max(int(limit), 0)
        self.window_seconds = max(int(window_seconds), 1)
        self._lock = threading.Lock()
        self._buckets: dict[int, tuple[float, int]] = {}

    def _prune(self, moment: float) -> None:
        """Drop windows that have already expired.

        Without this the map would keep one entry per user who ever asked a
        question, for the lifetime of the process. Called under the lock.
        """
        if len(self._buckets) < self.PRUNE_THRESHOLD:
            return
        cutoff = moment - self.window_seconds
        self._buckets = {
            user_id: bucket
            for user_id, bucket in self._buckets.items()
            if bucket[0] > cutoff
        }

    def check(self, user_id: int, *, now: float | None = None) -> RateLimitDecision:
        """Count one request against ``user_id`` and say whether it may run."""
        if self.limit <= 0:
            # A limit of zero disables limiting rather than blocking everyone;
            # blocking every request on a misconfiguration would be worse.
            return RateLimitDecision(allowed=True, remaining=-1, retry_after=0)

        moment = time.monotonic() if now is None else now
        with self._lock:
            self._prune(moment)
            window_start, count = self._buckets.get(user_id, (moment, 0))
            if moment - window_start >= self.window_seconds:
                window_start, count = moment, 0
            if count >= self.limit:
                elapsed = moment - window_start
                retry_after = max(1, int(self.window_seconds - elapsed) + 1)
                self._buckets[user_id] = (window_start, count)
                return RateLimitDecision(
                    allowed=False, remaining=0, retry_after=retry_after
                )
            count += 1
            self._buckets[user_id] = (window_start, count)
            return RateLimitDecision(
                allowed=True, remaining=self.limit - count, retry_after=0
            )

    def reset(self, user_id: int | None = None) -> None:
        with self._lock:
            if user_id is None:
                self._buckets.clear()
            else:
                self._buckets.pop(user_id, None)


def get_rate_limiter(app, *, limit: int, window_seconds: int) -> FixedWindowRateLimiter:
    """One limiter per application, created on first use."""
    limiter = app.extensions.get(APP_EXTENSION_KEY)
    if (
        limiter is None
        or limiter.limit != max(int(limit), 0)
        or limiter.window_seconds != max(int(window_seconds), 1)
    ):
        limiter = FixedWindowRateLimiter(limit=limit, window_seconds=window_seconds)
        app.extensions[APP_EXTENSION_KEY] = limiter
    return limiter


def reset_rate_limiter(app) -> None:
    """Drop all counters (tests, and a future admin action)."""
    limiter = app.extensions.get(APP_EXTENSION_KEY)
    if limiter is not None:
        limiter.reset()


__all__ = [
    "APP_EXTENSION_KEY",
    "FixedWindowRateLimiter",
    "RateLimitDecision",
    "get_rate_limiter",
    "reset_rate_limiter",
]
