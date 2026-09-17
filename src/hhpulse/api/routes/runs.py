from __future__ import annotations

from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status

from hhpulse.api.dependencies import get_container
from hhpulse.api.schemas import ManualRunResponse, RunProgressResponse
from hhpulse.bootstrap import Container

router = APIRouter(prefix="/api/v1/jobs", tags=["runs"])
ContainerDependency = Annotated[Container, Depends(get_container)]


@router.post(
    "/{job_id}/runs/today",
    response_model=ManualRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_today(job_id: str, container: ContainerDependency) -> ManualRunResponse:
    if container.scheduler is None:
        raise HTTPException(status_code=503, detail="crawl scheduler is not configured")
    try:
        accepted = await container.scheduler.trigger(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="analysis job not found") from exc
    return ManualRunResponse(accepted=accepted)


@router.get("/{job_id}/runs/today", response_model=RunProgressResponse)
async def get_today_progress(
    job_id: str,
    container: ContainerDependency,
) -> RunProgressResponse:
    job = await container.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="analysis job not found")
    timezone = ZoneInfo(job.schedule.timezone)
    observation_date = container.clock.now().astimezone(timezone).date()
    run = await container.executions.get_for_job_date(job.id, observation_date)
    if run is None:
        raise HTTPException(status_code=404, detail="today's crawl run has not started")
    progress = await container.executions.progress(run.id)
    return RunProgressResponse.from_domain(
        progress,
        error_code=run.error_code,
        error_message=run.error_message,
    )
