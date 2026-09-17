from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime

from hhpulse.domain.enums import RoleSelectionMode, RunStatus, RunUnitStatus, UserAgentMode
from hhpulse.domain.errors import DomainError, InvalidStateTransition
from hhpulse.domain.value_objects import (
    DailySchedule,
    Methodology,
    RateLimitPolicy,
    SearchQuery,
    unique_strings,
)


@dataclass(frozen=True, slots=True)
class AnalysisScope:
    region_ids: tuple[str, ...]
    role_selection_mode: RoleSelectionMode
    role_ids: tuple[str, ...] = ()
    include_experience_strata: bool = True

    def __post_init__(self) -> None:
        regions = unique_strings(self.region_ids, field_name="region_ids")
        roles = unique_strings(self.role_ids, field_name="role_ids")
        object.__setattr__(self, "region_ids", regions)
        object.__setattr__(self, "role_ids", roles)

        if not regions:
            raise DomainError("analysis scope must contain at least one region")
        if self.role_selection_mode is RoleSelectionMode.SELECTED and not roles:
            raise DomainError("selected role mode requires at least one role id")
        if self.role_selection_mode is RoleSelectionMode.ALL and roles:
            raise DomainError("all role mode must not contain explicit role ids")


@dataclass(frozen=True, slots=True)
class AnalysisJob:
    id: str
    name: str
    scope: AnalysisScope
    rate_limit: RateLimitPolicy
    user_agent_mode: UserAgentMode
    schedule: DailySchedule
    methodology: Methodology
    enabled: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainError("job id must not be empty")
        if not self.name.strip():
            raise DomainError("job name must not be empty")
        if self.updated_at < self.created_at:
            raise DomainError("updated_at must not be before created_at")

    def rename(self, name: str, *, at: datetime) -> AnalysisJob:
        if not name.strip():
            raise DomainError("job name must not be empty")
        return replace(self, name=name.strip(), updated_at=at)

    def set_enabled(self, enabled: bool, *, at: datetime) -> AnalysisJob:
        return replace(self, enabled=enabled, updated_at=at)


@dataclass(frozen=True, slots=True)
class CrawlRun:
    id: str
    job_id: str
    observation_date: date
    status: RunStatus = RunStatus.PLANNED
    total_units: int = 0
    completed_units: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.job_id.strip():
            raise DomainError("run id and job id must not be empty")
        if self.total_units < 0 or self.completed_units < 0:
            raise DomainError("run counters must not be negative")
        if self.completed_units > self.total_units:
            raise DomainError("completed units must not exceed total units")

    def start(self, *, total_units: int, at: datetime) -> CrawlRun:
        if self.status is not RunStatus.PLANNED:
            raise InvalidStateTransition(f"cannot start run from {self.status}")
        if total_units < 1:
            raise DomainError("run must contain at least one unit")
        return replace(
            self,
            status=RunStatus.RUNNING,
            total_units=total_units,
            started_at=at,
        )

    def mark_unit_completed(self) -> CrawlRun:
        if self.status not in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE}:
            raise InvalidStateTransition(f"cannot complete unit from {self.status}")
        if self.completed_units >= self.total_units:
            raise InvalidStateTransition("all run units are already completed")
        return replace(self, completed_units=self.completed_units + 1, status=RunStatus.RUNNING)

    def wait_for_source(self) -> CrawlRun:
        if self.status is not RunStatus.RUNNING:
            raise InvalidStateTransition(f"cannot wait for source from {self.status}")
        return replace(self, status=RunStatus.WAITING_SOURCE)

    def resume(self) -> CrawlRun:
        if self.status is not RunStatus.WAITING_SOURCE:
            raise InvalidStateTransition(f"cannot resume run from {self.status}")
        return replace(self, status=RunStatus.RUNNING)

    def parser_broken(self, *, message: str, at: datetime) -> CrawlRun:
        if self.status not in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE}:
            raise InvalidStateTransition(f"cannot break parser from {self.status}")
        return replace(
            self,
            status=RunStatus.PARSER_BROKEN,
            finished_at=at,
            error_code="PARSER_CONTRACT_BROKEN",
            error_message=message,
        )

    def fail(self, *, code: str, message: str, at: datetime) -> CrawlRun:
        terminal_statuses = {
            RunStatus.PARSER_BROKEN,
            RunStatus.FAILED,
            RunStatus.EXPIRED,
            RunStatus.SUCCEEDED,
        }
        if self.status in terminal_statuses:
            raise InvalidStateTransition(f"cannot fail run from {self.status}")
        return replace(
            self,
            status=RunStatus.FAILED,
            finished_at=at,
            error_code=code,
            error_message=message,
        )

    def expire(self, *, at: datetime) -> CrawlRun:
        if self.status not in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE}:
            raise InvalidStateTransition(f"cannot expire run from {self.status}")
        return replace(
            self,
            status=RunStatus.EXPIRED,
            finished_at=at,
            error_code="DAY_EXPIRED",
            error_message="daily crawl did not finish before the observation day ended",
        )

    def succeed(self, *, at: datetime) -> CrawlRun:
        if self.status not in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE}:
            raise InvalidStateTransition(f"cannot succeed run from {self.status}")
        if self.completed_units != self.total_units:
            raise InvalidStateTransition("cannot publish incomplete run")
        return replace(self, status=RunStatus.SUCCEEDED, finished_at=at)


@dataclass(frozen=True, slots=True)
class CrawlUnit:
    id: str
    run_id: str
    query: SearchQuery
    status: RunUnitStatus = RunUnitStatus.PENDING
    attempts: int = 0
    updated_at: datetime | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.run_id.strip():
            raise DomainError("crawl unit id and run id must not be empty")
        if self.attempts < 0:
            raise DomainError("crawl unit attempts must not be negative")

    def start_attempt(self, *, at: datetime) -> CrawlUnit:
        if self.status not in {RunUnitStatus.PENDING, RunUnitStatus.WAITING_RETRY}:
            raise InvalidStateTransition(f"cannot start crawl unit from {self.status}")
        return replace(
            self,
            status=RunUnitStatus.RUNNING,
            attempts=self.attempts + 1,
            updated_at=at,
            last_error=None,
        )

    def wait_retry(self, *, error: str, at: datetime) -> CrawlUnit:
        if self.status is not RunUnitStatus.RUNNING:
            raise InvalidStateTransition(f"cannot wait retry from {self.status}")
        return replace(
            self,
            status=RunUnitStatus.WAITING_RETRY,
            updated_at=at,
            last_error=error,
        )

    def succeed(self, *, at: datetime) -> CrawlUnit:
        if self.status is not RunUnitStatus.RUNNING:
            raise InvalidStateTransition(f"cannot succeed crawl unit from {self.status}")
        return replace(self, status=RunUnitStatus.SUCCEEDED, updated_at=at, last_error=None)

    def fail(self, *, error: str, at: datetime) -> CrawlUnit:
        if self.status not in {RunUnitStatus.RUNNING, RunUnitStatus.WAITING_RETRY}:
            raise InvalidStateTransition(f"cannot fail crawl unit from {self.status}")
        return replace(
            self,
            status=RunUnitStatus.FAILED,
            updated_at=at,
            last_error=error,
        )
