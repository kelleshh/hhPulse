from __future__ import annotations

from uuid import uuid4

from hhpulse.application.dto import CreateAnalysisJobCommand
from hhpulse.application.ports.clock import Clock
from hhpulse.application.ports.repositories import AnalysisJobRepository
from hhpulse.domain.entities import AnalysisJob, AnalysisScope
from hhpulse.domain.value_objects import DailySchedule, Methodology, RateLimitPolicy


class CreateAnalysisJob:
    def __init__(self, repository: AnalysisJobRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def execute(self, command: CreateAnalysisJobCommand) -> AnalysisJob:
        now = self._clock.now()
        job = AnalysisJob(
            id=str(uuid4()),
            name=command.name.strip(),
            scope=AnalysisScope(
                region_ids=command.region_ids,
                role_selection_mode=command.role_selection_mode,
                role_ids=command.role_ids,
                include_experience_strata=command.include_experience_strata,
            ),
            rate_limit=RateLimitPolicy(
                max_concurrency=command.max_concurrency,
                max_rps=command.max_rps,
            ),
            user_agent_mode=command.user_agent_mode,
            schedule=DailySchedule(timezone=command.timezone),
            methodology=Methodology(),
            enabled=command.enabled,
            created_at=now,
            updated_at=now,
        )
        await self._repository.add(job)
        return job


class ListAnalysisJobs:
    def __init__(self, repository: AnalysisJobRepository) -> None:
        self._repository = repository

    async def execute(self) -> tuple[AnalysisJob, ...]:
        return tuple(await self._repository.list())


class GetAnalysisJob:
    def __init__(self, repository: AnalysisJobRepository) -> None:
        self._repository = repository

    async def execute(self, job_id: str) -> AnalysisJob | None:
        return await self._repository.get(job_id)


class SetAnalysisJobEnabled:
    def __init__(self, repository: AnalysisJobRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def execute(self, job_id: str, *, enabled: bool) -> AnalysisJob | None:
        job = await self._repository.get(job_id)
        if job is None:
            return None
        updated = job.set_enabled(enabled, at=self._clock.now())
        await self._repository.update(updated)
        return updated
