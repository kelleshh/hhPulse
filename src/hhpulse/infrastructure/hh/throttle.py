from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from hhpulse.domain.value_objects import RateLimitPolicy


@dataclass(frozen=True, slots=True)
class BackoffSnapshot:
    multiplier: float
    consecutive_successes: int
    throttled_count: int


class AdaptiveThrottle:
    """Single-flight transport with a post-response truncated-normal delay.

    Every response is followed by a delay in [0.9, 1.8] seconds. HTTP 429/temporary source
    pressure only makes that delay longer; successes gradually restore the base distribution.
    """

    def __init__(
        self,
        policy: RateLimitPolicy,
        *,
        max_multiplier: float = 120.0,
        recovery_successes: int = 8,
        delay_min_seconds: float = 0.9,
        delay_max_seconds: float = 1.8,
        delay_mean_seconds: float = 1.35,
        delay_stddev_seconds: float = 0.15,
        random_source: random.Random | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if not 0 < delay_min_seconds < delay_max_seconds:
            raise ValueError("post-response delay bounds must be positive and ordered")
        if not delay_min_seconds <= delay_mean_seconds <= delay_max_seconds:
            raise ValueError("post-response delay mean must be inside its bounds")
        if delay_stddev_seconds <= 0:
            raise ValueError("post-response delay standard deviation must be positive")
        self._rate_multiplier = max(1.0, 1.0 / policy.max_rps)
        self._max_multiplier = max_multiplier
        self._recovery_successes = recovery_successes
        self._multiplier = 1.0
        self._consecutive_successes = 0
        self._throttled_count = 0
        self._delay_min_seconds = delay_min_seconds
        self._delay_max_seconds = delay_max_seconds
        self._delay_mean_seconds = delay_mean_seconds
        self._delay_stddev_seconds = delay_stddev_seconds
        self._random = random_source or random.Random()
        self._sleeper = sleeper
        # requests.Session is deliberately single-flight and is not shared concurrently.
        self._concurrency = asyncio.Semaphore(1)

    async def __aenter__(self) -> AdaptiveThrottle:
        await self._concurrency.acquire()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._concurrency.release()

    async def wait_after_response(self) -> None:
        await self._sleeper(self.next_delay_seconds())

    def next_delay_seconds(self) -> float:
        while True:
            delay = self._random.normalvariate(
                self._delay_mean_seconds,
                self._delay_stddev_seconds,
            )
            if self._delay_min_seconds <= delay <= self._delay_max_seconds:
                return delay * self._rate_multiplier * self._multiplier

    def on_throttled(self, *, retry_after_seconds: float | None = None) -> None:
        self._throttled_count += 1
        self._consecutive_successes = 0
        self._multiplier = min(self._max_multiplier, max(2.0, self._multiplier * 2.0))
        if retry_after_seconds is not None and retry_after_seconds > 0:
            minimum_multiplier = retry_after_seconds / self._delay_mean_seconds
            self._multiplier = min(
                self._max_multiplier,
                max(self._multiplier, minimum_multiplier),
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
