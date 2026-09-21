from hhpulse.domain.enums import UserAgentMode
from hhpulse.infrastructure.hh.user_agents import (
    DEFAULT_HEADERS,
    DEFAULT_USER_AGENT,
    UserAgentProvider,
)


def test_shared_mode_uses_one_user_agent_for_all_workers() -> None:
    provider = UserAgentProvider(UserAgentMode.SHARED, ("a", "b"))
    assert provider.for_worker(0) == "a"
    assert provider.for_worker(9) == "a"


def test_legacy_per_worker_mode_is_forced_to_one_stable_user_agent() -> None:
    provider = UserAgentProvider(UserAgentMode.PER_WORKER, ("a", "b"))
    assert [provider.for_worker(index) for index in range(4)] == ["a", "a", "a", "a"]


def test_default_headers_match_proven_standalone_collector() -> None:
    assert DEFAULT_USER_AGENT.endswith("Chrome/134.0.0.0 Safari/537.36")
    assert DEFAULT_HEADERS == {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
