from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from hhpulse.domain.entities import AnalysisJob, CrawlRun


class Sleeper(Protocol):
    async def sleep(self, seconds: float) -> None: ...


class HtmlQuarantine(Protocol):
    async def save(
        self,
        *,
        run_id: str,
        unit_id: str | None,
        html: str,
        observed_at: datetime,
    ) -> str: ...

    async def purge_expired(self, *, now: datetime) -> int: ...


class DailyCrawlExecutor(Protocol):
    async def execute(self, job: AnalysisJob, observation_date: date) -> CrawlRun: ...
