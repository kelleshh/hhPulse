from hhpulse.domain.enums import UserAgentMode
from hhpulse.infrastructure.hh.user_agents import UserAgentProvider


def test_shared_mode_uses_one_user_agent_for_all_workers() -> None:
    provider = UserAgentProvider(UserAgentMode.SHARED, ("a", "b"))
    assert provider.for_worker(0) == "a"
    assert provider.for_worker(9) == "a"


def test_per_worker_mode_rotates_deterministically() -> None:
    provider = UserAgentProvider(UserAgentMode.PER_WORKER, ("a", "b"))
    assert [provider.for_worker(index) for index in range(4)] == ["a", "b", "a", "b"]
