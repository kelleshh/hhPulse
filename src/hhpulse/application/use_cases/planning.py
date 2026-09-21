from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from hhpulse.application.ports.market_source import MarketSource
from hhpulse.domain.entities import AnalysisJob
from hhpulse.domain.enums import ExperienceBand, RoleSelectionMode, SearchTarget
from hhpulse.domain.value_objects import ProfessionalRole, SearchQuery

EXPERIENCE_STRATA: tuple[ExperienceBand, ...] = (
    ExperienceBand.ANY,
    ExperienceBand.NO_EXPERIENCE,
    ExperienceBand.BETWEEN_1_AND_3,
    ExperienceBand.BETWEEN_3_AND_6,
    ExperienceBand.MORE_THAN_6,
)


@dataclass(frozen=True, slots=True)
class CrawlPlan:
    roles: tuple[ProfessionalRole, ...]
    queries: tuple[SearchQuery, ...]


class BuildDailyCrawlPlan:
    """Builds a complete plan with one randomized role order shared by both phases."""

    def __init__(self, source: MarketSource, *, random_source: random.Random | None = None) -> None:
        self._source = source
        self._random = random_source or random.Random()

    async def execute(self, job: AnalysisJob, *, observation_date: date) -> CrawlPlan:
        roles = list(await self._resolve_roles(job))
        self._random.shuffle(roles)
        experience_bands = (
            EXPERIENCE_STRATA if job.scope.include_experience_strata else (ExperienceBand.ANY,)
        )
        queries = tuple(
            SearchQuery(
                target=target,
                observation_date=observation_date,
                region_id=region_id,
                professional_role_id=role.id,
                experience=experience,
            )
            for target in (SearchTarget.RESUME, SearchTarget.VACANCY)
            for region_id in sorted(job.scope.region_ids)
            for role in roles
            for experience in experience_bands
        )
        return CrawlPlan(roles=tuple(roles), queries=queries)

    async def _resolve_roles(self, job: AnalysisJob) -> Sequence[ProfessionalRole]:
        discovered: dict[str, ProfessionalRole] = {}
        for region_id in job.scope.region_ids:
            for role in await self._source.discover_roles(region_id=region_id):
                discovered.setdefault(role.id, role)

        if job.scope.role_selection_mode is RoleSelectionMode.ALL:
            return tuple(discovered.values())

        missing = [role_id for role_id in job.scope.role_ids if role_id not in discovered]
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"selected HH roles were not discovered: {missing_text}")
        return tuple(discovered[role_id] for role_id in job.scope.role_ids)
