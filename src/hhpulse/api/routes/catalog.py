from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from hhpulse.api.dependencies import get_container
from hhpulse.api.schemas import RoleResponse
from hhpulse.application.errors import MarketSourceUnavailable
from hhpulse.bootstrap import Container

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])
ContainerDependency = Annotated[Container, Depends(get_container)]


@router.get("/professional-roles", response_model=list[RoleResponse])
async def list_professional_roles(container: ContainerDependency) -> list[RoleResponse]:
    if container.role_catalog is None:
        raise HTTPException(status_code=503, detail="professional role catalog is not configured")
    try:
        roles = await container.role_catalog.list_roles()
    except MarketSourceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [RoleResponse(id=role.id, name=role.name) for role in roles]
