from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from hhpulse.domain.value_objects import RateLimitPolicy


@dataclass(frozen=True, slots=True)
class BackoffSnapshot:
    multiplier: float
    consecutive_successes: int
    throttled_count: int


class AdaptiveThrottle:
    """Global deterministic rate limiter with adaptive 429 backoff.

    Requests are paced only by the configured RPS/concurrency policy and
    server-provided Retry-After backoff. Client identity stays stable.
    """

    def __init__(
        self,
        policy: RateLimitPolicy,
        *,
        max_multiplier: float = 120.0,
        recovery_successes: int = 8,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base_interval = 1.0 / policy.max_rps
        self._max_multiplier = max_multiplier
        self._recovery_successes = recovery_successes
        self._multiplier = 1.0
        self._consecutive_successes = 0
        self._throttled_count = 0
        self._sleeper = sleeper
        self._monotonic = monotonic
        self._next_allowed = 0.0
        self._rate_lock = asyncio.Lock()
        self._concurrency = asyncio.Semaphore(policy.max_concurrency)

    async def __aenter__(self) -> AdaptiveThrottle:
        await self._concurrency.acquire()
        async with self._rate_lock:
            now = self._monotonic()
            if self._next_allowed > now:
                await self._sleeper(self._next_allowed - now)
                now = self._monotonic()
            self._next_allowed = now + self._base_interval * self._multiplier
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._concurrency.release()

    async def wait_after_response(self) -> None:
        """Legacy no-op kept for old callers/tests during migration."""

    def next_delay_seconds(self) -> float:
        return self._base_interval * self._multiplier

    def on_throttled(self, *, retry_after_seconds: float | None = None) -> None:
        self._throttled_count += 1
        self._consecutive_successes = 0
        self._multiplier = min(self._max_multiplier, max(2.0, self._multiplier * 2.0))
        if retry_after_seconds is not None and retry_after_seconds > 0:
            minimum_multiplier = retry_after_seconds / self._base_interval
            self._multiplier = min(
                self._max_multiplier,
                max(self._multiplier, minimum_multiplier),
            )
        self._next_allowed = max(
            self._next_allowed,
            self._monotonic() + self._base_interval * self._multiplier,
        )

    def on_unavailable(self) -> None:
        self._consecutive_successes = 0
        self._multiplier = min(self._max_multiplier, max(2.0, self._multiplier * 2.0))

    def on_success(self) -> None:
        self._consecutive_successes += 1
        if self._consecutive_successes < self._recovery_successes:
            return
        self._multiplier = max(1.0, self._multiplier / 2.0)
        self._consecutive_successes = 0

    def snapshot(self) -> BackoffSnapshot:
        return BackoffSnapshot(
            multiplier=self._multiplier,
            consecutive_successes=self._consecutive_successes,
            throttled_count=self._throttled_count,
        )
