from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hhpulse.api.routes import health, jobs
from hhpulse.bootstrap import Container, build_container
from hhpulse.config import Settings


def create_app(
    *,
    container: Container | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container or await build_container(settings)
        yield

    app = FastAPI(
        title="hhPulse",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(jobs.router)
    return app
