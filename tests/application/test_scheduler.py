from __future__ import annotations

import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from hhpulse.application.scheduler import DailyCrawlScheduler
from hhpulse.domain.entities import AnalysisJob, AnalysisScope
from hhpulse.domain.enums import RoleSelectionMode, UserAgentMode
from hhpulse.domain.value_objects import DailySchedule, Methodology, RateLimitPolicy


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))

    def today(self) -> date:
        return self.now().date()


class MemoryJobs:
    def __init__(self, job: AnalysisJob) -> None:
        self.job = job

    async def get(self, job_id: str) -> AnalysisJob | None:
        return self.job if job_id == self.job.id else None

    async def list(self) -> tuple[AnalysisJob, ...]:
        return (self.job,)


class NoRuns:
    async def get_for_job_date(self, job_id: str, observation_date: date):
        return None


class BlockingExecutor:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def execute(self, job: AnalysisJob, observation_date: date) -> None:
        self.calls += 1
        self.started.set()
        await self.release.wait()


class YieldingSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(0)


async def test_scheduler_never_launches_duplicate_task_for_same_job() -> None:
    clock = FixedClock()
    job = _job(clock.now())
    executor = BlockingExecutor()
    scheduler = DailyCrawlScheduler(
        MemoryJobs(job),
        NoRuns(),
        executor,
        clock,
        YieldingSleeper(),
    )

    await scheduler.run_once()
    await executor.started.wait()
    await scheduler.run_once()

    assert executor.calls == 1
    executor.release.set()
    await asyncio.sleep(0)
    await scheduler.stop()


async def test_manual_trigger_rejects_unknown_job() -> None:
    clock = FixedClock()
    job = _job(clock.now())
    scheduler = DailyCrawlScheduler(
        MemoryJobs(job),
        NoRuns(),
        BlockingExecutor(),
        clock,
        YieldingSleeper(),
    )

    with pytest.raises(KeyError, match="does not exist"):
        await scheduler.trigger("missing")


async def test_disabling_job_cancels_its_active_runtime_task() -> None:
    clock = FixedClock()
    job = _job(clock.now())
    jobs = MemoryJobs(job)
    executor = BlockingExecutor()
    scheduler = DailyCrawlScheduler(
        jobs,
        NoRuns(),
        executor,
        clock,
        YieldingSleeper(),
    )
    await scheduler.run_once()
    await executor.started.wait()

    jobs.job = job.set_enabled(False, at=clock.now())
    await scheduler.run_once()

    assert executor.calls == 1
    await scheduler.stop()


def _job(now: datetime) -> AnalysisJob:
    return AnalysisJob(
        id="job-1",
        name="Москва",
        scope=AnalysisScope(region_ids=("1",), role_selection_mode=RoleSelectionMode.ALL),
        rate_limit=RateLimitPolicy(),
        user_agent_mode=UserAgentMode.SHARED,
        schedule=DailySchedule(),
        methodology=Methodology(),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
