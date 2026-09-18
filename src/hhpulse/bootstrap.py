from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from hhpulse.application.ports.analytics import AnalyticsReadRepository
from hhpulse.application.ports.catalog import ProfessionalRoleCatalog
from hhpulse.application.ports.clock import Clock
from hhpulse.application.ports.repositories import (
    AnalysisJobRepository,
    CrawlExecutionRepository,
)
from hhpulse.application.scheduler import DailyCrawlScheduler
from hhpulse.application.use_cases.execution import ExecuteDailyCrawl
from hhpulse.config import Settings
from hhpulse.domain.value_objects import RetryPolicy
from hhpulse.infrastructure.clock import SystemClock
from hhpulse.infrastructure.hh.catalog import HhProfessionalRoleCatalog
from hhpulse.infrastructure.hh.factory import HhMarketSourceFactory
from hhpulse.infrastructure.persistence.analytics import SqliteAnalyticsReadRepository
from hhpulse.infrastructure.persistence.database import SqliteDatabase
from hhpulse.infrastructure.persistence.repositories import (
    SqliteAnalysisJobRepository,
    SqliteCrawlExecutionRepository,
)
from hhpulse.infrastructure.runtime import AsyncioSleeper, FileHtmlQuarantine


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    clock: Clock
    jobs: AnalysisJobRepository
    executions: CrawlExecutionRepository
    scheduler: DailyCrawlScheduler | None = None
    analytics: AnalyticsReadRepository | None = None
    role_catalog: ProfessionalRoleCatalog | None = None


async def build_container(settings: Settings | None = None) -> Container:
    resolved = settings or Settings.from_env()
    database = SqliteDatabase(resolved.db_path)
    await database.initialize()
    clock = SystemClock("UTC")
    sleeper = AsyncioSleeper()
    jobs = SqliteAnalysisJobRepository(database)
    executions = SqliteCrawlExecutionRepository(database)
    analytics = SqliteAnalyticsReadRepository(database)
    quarantine = FileHtmlQuarantine(
        resolved.quarantine_dir,
        retention=timedelta(hours=resolved.quarantine_retention_hours),
    )
    retry_policy = RetryPolicy(
        initial_delay_seconds=resolved.retry_initial_seconds,
        max_delay_seconds=resolved.retry_max_seconds,
    )
    executor = ExecuteDailyCrawl(
        executions,
        HhMarketSourceFactory(timeout_seconds=resolved.source_timeout_seconds),
        quarantine,
        clock,
        sleeper,
        retry_policy,
        preflight_successes=resolved.preflight_successes,
    )
    scheduler = DailyCrawlScheduler(
        jobs,
        executions,
        executor,
        clock,
        sleeper,
        poll_seconds=resolved.scheduler_poll_seconds,
    )
    return Container(
        settings=resolved,
        clock=clock,
        jobs=jobs,
        executions=executions,
        scheduler=scheduler,
        analytics=analytics,
        role_catalog=HhProfessionalRoleCatalog(
            timeout_seconds=resolved.source_timeout_seconds,
        ),
    )
