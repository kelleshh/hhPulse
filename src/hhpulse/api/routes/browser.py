from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from hhpulse.api.dependencies import get_container
from hhpulse.bootstrap import Container

router = APIRouter(prefix="/api/v1/browser", tags=["browser"])


class BrowserAnswer(BaseModel):
    command_id: str
    result: dict[str, Any] = Field(max_length=30)


def authorized(
    container: Annotated[Container, Depends(get_container)],
    x_hhpulse_browser_token: Annotated[str | None, Header()] = None,
) -> Container:
    if not container.settings.browser_token or not secrets.compare_digest(
        x_hhpulse_browser_token or "", container.settings.browser_token
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid browser token")
    return container


@router.get("/next")
async def next_command(container: Annotated[Container, Depends(authorized)]) -> dict[str, Any]:
    if container.browser_bridge is None:
        raise HTTPException(status_code=503, detail="browser bridge unavailable")
    return {"command": await container.browser_bridge.next_command()}


@router.post("/result")
async def submit_result(
    answer: BrowserAnswer,
    container: Annotated[Container, Depends(authorized)],
) -> dict[str, bool]:
    if container.browser_bridge is None:
        raise HTTPException(status_code=503, detail="browser bridge unavailable")
    accepted = await container.browser_bridge.submit(answer.command_id, answer.result)
    return {"accepted": accepted}
