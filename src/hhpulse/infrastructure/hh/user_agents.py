from __future__ import annotations

from hhpulse.domain.enums import UserAgentMode

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

_DEFAULT_USER_AGENTS: tuple[str, ...] = (
    DEFAULT_USER_AGENT,
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
        # PER_WORKER is retained only to deserialize databases made by older
        # versions. Network traffic always uses one stable identity now.
        return self._user_agents[0]
