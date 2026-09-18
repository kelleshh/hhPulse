from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from hhpulse.application.ports.repositories import CrawlProgress
from hhpulse.domain.entities import AnalysisJob
from hhpulse.domain.enums import RoleSelectionMode, RunStatus, UserAgentMode


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    region_ids: list[str] = Field(min_length=1)
    role_selection_mode: RoleSelectionMode = RoleSelectionMode.ALL
    role_ids: list[str] = Field(default_factory=list)
    max_concurrency: int = Field(default=1, ge=1, le=32)
    max_rps: float = Field(default=0.5, gt=0, le=20)
    user_agent_mode: UserAgentMode = UserAgentMode.SHARED
    timezone: str = "Europe/Moscow"
    enabled: bool = True
    include_experience_strata: bool = True


class SetJobEnabledRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class JobResponse(BaseModel):
    id: str
    name: str
    region_ids: list[str]
    role_selection_mode: RoleSelectionMode
    role_ids: list[str]
    include_experience_strata: bool
    max_concurrency: int
    max_rps: float
    user_agent_mode: UserAgentMode
    timezone: str
    methodology_version: str
    active_resume_window_days: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, job: AnalysisJob) -> JobResponse:
        return cls(
            id=job.id,
            name=job.name,
            region_ids=list(job.scope.region_ids),
            role_selection_mode=job.scope.role_selection_mode,
            role_ids=list(job.scope.role_ids),
            include_experience_strata=job.scope.include_experience_strata,
            max_concurrency=job.rate_limit.max_concurrency,
            max_rps=job.rate_limit.max_rps,
            user_agent_mode=job.user_agent_mode,
            timezone=job.schedule.timezone,
            methodology_version=job.methodology.version,
            active_resume_window_days=job.methodology.active_resume_window_days,
            enabled=job.enabled,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class ManualRunResponse(BaseModel):
    accepted: bool


class RunProgressResponse(BaseModel):
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
    error_code: str | None
    error_message: str | None

    @classmethod
    def from_domain(
        cls,
        progress: CrawlProgress,
        *,
        error_code: str | None,
        error_message: str | None,
    ) -> RunProgressResponse:
        return cls(
            run_id=progress.run_id,
            status=progress.status,
            total_units=progress.total_units,
            completed_units=progress.completed_units,
            pending_units=progress.pending_units,
            running_units=progress.running_units,
            waiting_retry_units=progress.waiting_retry_units,
            failed_units=progress.failed_units,
            total_attempts=progress.total_attempts,
            next_retry_at=progress.next_retry_at,
            error_code=error_code,
            error_message=error_message,
        )


class RoleResponse(BaseModel):
    id: str
    name: str


class RunEventResponse(BaseModel):
    id: int
    run_id: str
    unit_id: str | None
    occurred_at: datetime
    level: str
    event_type: str
    message: str
