from __future__ import annotations

from fastapi import Request

from hhpulse.bootstrap import Container


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("application container is not initialized")
    return container
