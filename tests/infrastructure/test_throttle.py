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
