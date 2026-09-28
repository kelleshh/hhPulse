from __future__ import annotations

import asyncio
import logging
from datetime import date
from zoneinfo import ZoneInfo

from hhpulse.application.ports.clock import Clock
from hhpulse.application.ports.repositories import (
    AnalysisJobRepository,
    CrawlExecutionRepository,
)
from hhpulse.application.ports.runtime import DailyCrawlExecutor, Sleeper
from hhpulse.domain.entities import AnalysisJob
from hhpulse.domain.enums import RunStatus

LOGGER = logging.getLogger(__name__)


class DailyCrawlScheduler:
    def __init__(
        self,
        jobs: AnalysisJobRepository,
        executions: CrawlExecutionRepository,
        executor: DailyCrawlExecutor,
        clock: Clock,
        sleeper: Sleeper,
        *,
        poll_seconds: float = 30.0,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("scheduler poll interval must be positive")
        self._jobs = jobs
        self._executions = executions
        self._executor = executor
        self._clock = clock
        self._sleeper = sleeper
        self._poll_seconds = poll_seconds
        self._loop_task: asyncio.Task[None] | None = None
        self._active: dict[str, asyncio.Task[None]] = {}
        self._stopping = False

    async def start(self) -> None:
        if self._loop_task is not None:
            return
        self._stopping = False
        self._loop_task = asyncio.create_task(self._run_loop(), name="hhpulse-scheduler")

    async def stop(self) -> None:
        self._stopping = True
        tasks = [task for task in self._active.values() if not task.done()]
        if self._loop_task is not None:
            self._loop_task.cancel()
            tasks.append(self._loop_task)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._active.clear()
        self._loop_task = None

    async def trigger(self, job_id: str) -> bool:
        job = await self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"analysis job {job_id!r} does not exist")
        observation_date = self._observation_date(job)
        existing = await self._executions.get_for_job_date(job.id, observation_date)
        if existing is not None and existing.status is RunStatus.PARSER_BROKEN:
            await self._executions.reopen_parser_broken(existing.id, at=self._clock.now())
        return await self._launch_if_due(job)

    async def cancel(self, job_id: str) -> None:
        """Stop an active crawl before its job and persisted aggregate are deleted."""
        await self._cancel_active(job_id)

    async def run_once(self) -> None:
        self._remove_finished_tasks()
        for job in await self._jobs.list():
            if job.enabled:
                await self._launch_if_due(job)
            else:
                await self._cancel_active(job.id)

    async def _run_loop(self) -> None:
        while not self._stopping:
            try:
                await self.run_once()
            except Exception:
                LOGGER.exception("scheduler tick failed")
            await self._sleeper.sleep(self._poll_seconds)

    async def _launch_if_due(self, job: AnalysisJob) -> bool:
        active = self._active.get(job.id)
        if active is not None and not active.done():
            return False
        observation_date = self._observation_date(job)
        existing = await self._executions.get_for_job_date(job.id, observation_date)
        if existing is not None and existing.finished_at is not None:
            return False
        task = asyncio.create_task(
            self._execute(job, observation_date),
            name=f"hhpulse-job-{job.id}-{observation_date.isoformat()}",
        )
        self._active[job.id] = task
        return True

    async def _execute(self, job: AnalysisJob, observation_date: date) -> None:
        try:
            await self._executor.execute(job, observation_date)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception(
                "daily crawl task crashed",
                extra={"job_id": job.id, "observation_date": observation_date.isoformat()},
            )

    async def _cancel_active(self, job_id: str) -> None:
        task = self._active.pop(job_id, None)
        if task is None or task.done():
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    def _remove_finished_tasks(self) -> None:
        self._active = {job_id: task for job_id, task in self._active.items() if not task.done()}

    def _observation_date(self, job: AnalysisJob) -> date:
        timezone = ZoneInfo(job.schedule.timezone)
        return self._clock.now().astimezone(timezone).date()
