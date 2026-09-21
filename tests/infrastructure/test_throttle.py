import random

from hhpulse.domain.value_objects import RateLimitPolicy
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle


def test_429_only_slows_down_and_successes_gradually_recover() -> None:
    throttle = AdaptiveThrottle(
        RateLimitPolicy(max_concurrency=1, max_rps=1.0),
        recovery_successes=2,
    )

    throttle.on_throttled()
    assert throttle.snapshot().multiplier == 2.0

    throttle.on_success()
    assert throttle.snapshot().multiplier == 2.0
    throttle.on_success()
    assert throttle.snapshot().multiplier == 1.0


def test_post_response_delay_is_truncated_normal_inside_requested_bounds() -> None:
    throttle = AdaptiveThrottle(
        RateLimitPolicy(),
        random_source=random.Random(42),
    )

    delays = [throttle.next_delay_seconds() for _ in range(2_000)]

    assert min(delays) >= 0.9
    assert max(delays) <= 1.8
    assert 1.32 <= sum(delays) / len(delays) <= 1.38
