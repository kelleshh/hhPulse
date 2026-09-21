from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from hhpulse.domain.entities import AnalysisJob, CrawlRun, CrawlUnit
from hhpulse.domain.enums import RunStatus
from hhpulse.domain.value_objects import SearchObservation


@dataclass(frozen=True, slots=True)
class CrawlProgress:
    run_id: str
    status: RunStatus
    total_units: int
    completed_units: int
    pending_units: int
    running_units: int
    waiting_retry_units: int
    failed_units: int
    total_attempts: int
    next_retry_at: datetime | None


@dataclass(frozen=True, slots=True)
class CrawlEvent:
    id: int
    run_id: str
    unit_id: str | None
    occurred_at: datetime
    level: str
    event_type: str
    message: str


class AnalysisJobRepository(Protocol):
    async def add(self, job: AnalysisJob) -> None: ...

    async def get(self, job_id: str) -> AnalysisJob | None: ...

    async def list(self) -> Sequence[AnalysisJob]: ...

    async def update(self, job: AnalysisJob) -> None: ...

    async def delete(self, job_id: str) -> bool: ...


class CrawlExecutionRepository(Protocol):
    """Transactional persistence boundary for the complete CrawlRun aggregate."""

    async def get_or_create(self, run: CrawlRun) -> CrawlRun: ...

    async def get(self, run_id: str) -> CrawlRun | None: ...

    async def get_for_job_date(
        self,
        job_id: str,
        observation_date: date,
    ) -> CrawlRun | None: ...

    async def initialize(self, run: CrawlRun, units: Sequence[CrawlUnit]) -> CrawlRun: ...

    async def recover_interrupted(self, run_id: str, *, at: datetime) -> int: ...

    async def claim_next_ready(
        self,
        run_id: str,
        *,
        worker_id: str,
        at: datetime,
    ) -> CrawlUnit | None: ...

    async def defer_unit(
        self,
        unit_id: str,
        *,
        error: str,
        retry_at: datetime,
        at: datetime,
    ) -> None: ...

    async def complete_unit(
        self,
        unit_id: str,
        observation: SearchObservation,
        *,
        at: datetime,
    ) -> CrawlRun: ...

    async def abort_parser(
        self,
        run_id: str,
        *,
        message: str,
        at: datetime,
    ) -> CrawlRun: ...

    async def reopen_parser_broken(self, run_id: str, *, at: datetime) -> CrawlRun: ...

    async def fail_run(
        self,
        run_id: str,
        *,
        code: str,
        message: str,
        at: datetime,
    ) -> CrawlRun: ...

    async def expire_run(self, run_id: str, *, at: datetime) -> CrawlRun: ...

    async def publish_completed(self, run_id: str, *, at: datetime) -> CrawlRun: ...

    async def progress(self, run_id: str) -> CrawlProgress: ...

    async def list_units(self, run_id: str) -> Sequence[CrawlUnit]: ...

    async def list_events(self, run_id: str, *, limit: int = 200) -> Sequence[CrawlEvent]: ...
