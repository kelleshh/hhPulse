from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from hhpulse.api.dependencies import get_container
from hhpulse.application.analytics import MarketAnalytics
from hhpulse.bootstrap import Container

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
ContainerDependency = Annotated[Container, Depends(get_container)]


@router.get("")
async def list_alerts(container: ContainerDependency) -> list[dict[str, Any]]:
    if container.analytics is None:
        raise HTTPException(status_code=503, detail="analytics read model is not configured")
    return await MarketAnalytics(container.analytics).alerts(today=container.clock.today())


@router.post("/{alert_id:path}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_alert(alert_id: str, container: ContainerDependency) -> Response:
    if container.analytics is None:
        raise HTTPException(status_code=503, detail="analytics read model is not configured")
    await container.analytics.resolve_alert(alert_id, at=container.clock.now())
    return Response(status_code=status.HTTP_204_NO_CONTENT)
