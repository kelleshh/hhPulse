from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from hhpulse.api.dependencies import get_container
from hhpulse.api.schemas import CreateJobRequest, JobResponse, SetJobEnabledRequest
from hhpulse.application.dto import CreateAnalysisJobCommand
from hhpulse.application.use_cases.jobs import (
    CreateAnalysisJob,
    DeleteAnalysisJob,
    GetAnalysisJob,
    ListAnalysisJobs,
    SetAnalysisJobEnabled,
)
from hhpulse.bootstrap import Container
from hhpulse.domain.errors import DomainError

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
ContainerDependency = Annotated[Container, Depends(get_container)]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: CreateJobRequest,
    container: ContainerDependency,
) -> JobResponse:
    use_case = CreateAnalysisJob(container.jobs, container.clock)
    command = CreateAnalysisJobCommand(
        name=request.name,
        region_ids=tuple(request.region_ids),
        role_selection_mode=request.role_selection_mode,
        role_ids=tuple(request.role_ids),
        max_concurrency=request.max_concurrency,
        max_rps=request.max_rps,
        user_agent_mode=request.user_agent_mode,
        timezone=request.timezone,
        enabled=request.enabled,
        include_experience_strata=request.include_experience_strata,
    )
    try:
        job = await use_case.execute(command)
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JobResponse.from_domain(job)


@router.get("", response_model=list[JobResponse])
async def list_jobs(container: ContainerDependency) -> list[JobResponse]:
    jobs = await ListAnalysisJobs(container.jobs).execute()
    return [JobResponse.from_domain(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    container: ContainerDependency,
) -> JobResponse:
    job = await GetAnalysisJob(container.jobs).execute(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="analysis job not found")
    return JobResponse.from_domain(job)


@router.patch("/{job_id}/enabled", response_model=JobResponse)
async def set_job_enabled(
    job_id: str,
    request: SetJobEnabledRequest,
    container: ContainerDependency,
) -> JobResponse:
    job = await SetAnalysisJobEnabled(container.jobs, container.clock).execute(
        job_id,
        enabled=request.enabled,
    )
    if job is None:
        raise HTTPException(status_code=404, detail="analysis job not found")
    return JobResponse.from_domain(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_job(job_id: str, container: ContainerDependency) -> Response:
    if await container.jobs.get(job_id) is None:
        raise HTTPException(status_code=404, detail="analysis job not found")
    if container.scheduler is not None:
        await container.scheduler.cancel(job_id)
    deleted = await DeleteAnalysisJob(container.jobs).execute(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="analysis job not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
