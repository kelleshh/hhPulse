from __future__ import annotations

from dataclasses import dataclass

from hhpulse.application.ports.clock import Clock
from hhpulse.application.ports.repositories import (
    AnalysisJobRepository,
    CrawlRunRepository,
    CrawlUnitRepository,
    ObservationRepository,
)
from hhpulse.config import Settings
from hhpulse.infrastructure.clock import SystemClock
from hhpulse.infrastructure.persistence.database import SqliteDatabase
from hhpulse.infrastructure.persistence.repositories import (
    SqliteAnalysisJobRepository,
    SqliteCrawlRunRepository,
    SqliteCrawlUnitRepository,
    SqliteObservationRepository,
)


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    clock: Clock
    jobs: AnalysisJobRepository
    runs: CrawlRunRepository
    units: CrawlUnitRepository
    observations: ObservationRepository


async def build_container(settings: Settings | None = None) -> Container:
    resolved = settings or Settings.from_env()
    database = SqliteDatabase(resolved.db_path)
    await database.initialize()
    return Container(
        settings=resolved,
        clock=SystemClock(),
        jobs=SqliteAnalysisJobRepository(database),
        runs=SqliteCrawlRunRepository(database),
        units=SqliteCrawlUnitRepository(database),
        observations=SqliteObservationRepository(database),
    )
