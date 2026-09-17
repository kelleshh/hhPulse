from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from hhpulse.domain.value_objects import RateLimitPolicy


@dataclass(frozen=True, slots=True)
class BackoffSnapshot:
    multiplier: float
    consecutive_successes: int
    throttled_count: int


class AdaptiveThrottle:
    """Global request pacing plus conservative adaptive backoff.

    It never exceeds the user configured max RPS. HTTP 429/temporary source pressure only
    makes the crawler slower; repeated successful requests slowly restore the configured pace.
    """

    def __init__(
        self,
        policy: RateLimitPolicy,
        *,
        max_multiplier: float = 120.0,
        recovery_successes: int = 8,
    ) -> None:
        self._policy = policy
        self._max_multiplier = max_multiplier
        self._recovery_successes = recovery_successes
        self._multiplier = 1.0
        self._consecutive_successes = 0
        self._throttled_count = 0
        self._next_request_at = 0.0
        self._pace_lock = asyncio.Lock()
        self._concurrency = asyncio.Semaphore(policy.max_concurrency)

    async def __aenter__(self) -> AdaptiveThrottle:
        await self._concurrency.acquire()
        try:
            await self._wait_for_global_pace()
        except BaseException:
            self._concurrency.release()
            raise
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._concurrency.release()

    async def _wait_for_global_pace(self) -> None:
        async with self._pace_lock:
            now = time.monotonic()
            wait_seconds = max(0.0, self._next_request_at - now)
            if wait_seconds:
                await asyncio.sleep(wait_seconds)
            interval = self._multiplier / self._policy.max_rps
            self._next_request_at = time.monotonic() + interval

    def on_throttled(self, *, retry_after_seconds: float | None = None) -> None:
        self._throttled_count += 1
        self._consecutive_successes = 0
        self._multiplier = min(self._max_multiplier, max(2.0, self._multiplier * 2.0))
        if retry_after_seconds is not None and retry_after_seconds > 0:
            minimum_multiplier = retry_after_seconds * self._policy.max_rps
            self._multiplier = min(
                self._max_multiplier,
                max(self._multiplier, minimum_multiplier),
            )

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
