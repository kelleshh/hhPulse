from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from hhpulse.api.routes import alerts, analytics, catalog, health, jobs, runs
from hhpulse.bootstrap import Container, build_container
from hhpulse.config import Settings


def create_app(
    *,
    container: Container | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_container = container or await build_container(settings)
        app.state.container = resolved_container
        if resolved_container.scheduler is not None:
            await resolved_container.scheduler.start()
        try:
            yield
        finally:
            if resolved_container.scheduler is not None:
                await resolved_container.scheduler.stop()

    app = FastAPI(
        title="hhPulse",
        version="0.3.1",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(runs.router)
    app.include_router(catalog.router)
    app.include_router(analytics.router)
    app.include_router(alerts.router)
    return app
