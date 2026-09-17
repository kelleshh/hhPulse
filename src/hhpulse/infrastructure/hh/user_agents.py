from __future__ import annotations

from hhpulse.domain.enums import UserAgentMode

_DEFAULT_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.6 Safari/605.1.15",
)


class UserAgentProvider:
    def __init__(
        self,
        mode: UserAgentMode,
        user_agents: tuple[str, ...] = _DEFAULT_USER_AGENTS,
    ) -> None:
        if not user_agents:
            raise ValueError("at least one user-agent is required")
        self._mode = mode
        self._user_agents = user_agents

    def for_worker(self, worker_index: int) -> str:
        if worker_index < 0:
            raise ValueError("worker index must not be negative")
        if self._mode is UserAgentMode.SHARED:
            return self._user_agents[0]
        return self._user_agents[worker_index % len(self._user_agents)]
