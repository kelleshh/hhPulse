from __future__ import annotations

from dataclasses import dataclass

from hhpulse.domain.enums import RoleSelectionMode, UserAgentMode


@dataclass(frozen=True, slots=True)
class CreateAnalysisJobCommand:
    name: str
    region_ids: tuple[str, ...]
    role_selection_mode: RoleSelectionMode
    role_ids: tuple[str, ...]
    max_concurrency: int
    max_rps: float
    user_agent_mode: UserAgentMode
    timezone: str = "Europe/Moscow"
    enabled: bool = True
    include_experience_strata: bool = False
