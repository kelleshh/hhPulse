from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from hhpulse.domain.entities import CrawlRun
from hhpulse.domain.value_objects import SearchObservation


@dataclass(frozen=True, slots=True)
class PublishedObservation:
    observation: SearchObservation
    published_at: datetime


@dataclass(frozen=True, slots=True)
class RunRecord:
    run: CrawlRun
    job_name: str


class AnalyticsReadRepository(Protocol):
    async def list_observations(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> Sequence[PublishedObservation]: ...

    async def list_runs(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> Sequence[RunRecord]: ...

    async def resolve_alert(self, alert_id: str, *, at: datetime) -> None: ...

    async def list_resolved_alert_ids(self) -> set[str]: ...
