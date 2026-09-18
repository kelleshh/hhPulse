from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from hhpulse.api.dependencies import get_container
from hhpulse.application.analytics import MarketAnalytics
from hhpulse.bootstrap import Container

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
ContainerDependency = Annotated[Container, Depends(get_container)]


def service(container: Container) -> MarketAnalytics:
    if container.analytics is None:
        raise HTTPException(status_code=503, detail="analytics read model is not configured")
    return MarketAnalytics(container.analytics)


@router.get("/overview")
async def overview(
    container: ContainerDependency,
    metric: str = "hhIndex",
) -> dict[str, Any]:
    try:
        payload = await service(container).overview(metric=metric, today=container.clock.today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    active = await _active_progress(container)
    payload["activeRun"] = active
    return payload


@router.get("/comparison")
async def comparison(
    container: ContainerDependency,
    role_ids: str = "",
    comparison_mode: str = "roles",
    metric: str = "hhIndex",
    experience: str = "any",
    experience_strata: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict[str, Any]]:
    date_to = date_to or container.clock.today()
    date_from = date_from or date_to - timedelta(days=89)
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    try:
        return await service(container).comparison(
            metric=metric,
            comparison_mode=comparison_mode,
            role_ids=[item for item in role_ids.split(",") if item],
            experience=experience,
            experience_strata=[item for item in experience_strata.split(",") if item],
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/snapshot")
async def snapshot(
    container: ContainerDependency,
    date: date,
    role_id: str,
) -> dict[str, Any]:
    try:
        return await service(container).snapshot(observation_date=date, role_id=role_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/role-matrix")
async def role_matrix(
    container: ContainerDependency,
    date_to: date | None = None,
    history_days: Annotated[int, Query(ge=1, le=365)] = 90,
) -> dict[str, Any]:
    selected_date = date_to or container.clock.today()
    return await service(container).role_matrix(date_to=selected_date, history_days=history_days)


async def _active_progress(container: Container) -> dict[str, Any] | None:
    if container.analytics is None:
        return None
    today = container.clock.today()
    runs = await container.analytics.list_runs(date_from=today, date_to=today)
    active = next(
        (
            record.run
            for record in reversed(runs)
            if record.run.status.value in {"planned", "running", "waiting_source"}
        ),
        None,
    )
    if active is None:
        return None
    progress = await container.executions.progress(active.id)
    return {
        "runId": progress.run_id,
        "jobId": active.job_id,
        "status": progress.status.value,
        "totalUnits": progress.total_units,
        "completedUnits": progress.completed_units,
        "pendingUnits": progress.pending_units,
        "runningUnits": progress.running_units,
        "waitingRetryUnits": progress.waiting_retry_units,
        "failedUnits": progress.failed_units,
        "totalAttempts": progress.total_attempts,
        "nextRetryAt": progress.next_retry_at,
        "errorCode": active.error_code,
        "errorMessage": active.error_message,
        "startedAt": active.started_at,
    }
