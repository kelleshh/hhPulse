from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime
from typing import Any

from hhpulse.application.errors import MarketSourceUnavailable


class BrowserBridge:
    """One in-memory command slot served by the visible Chrome companion tab."""

    def __init__(self) -> None:
        self._pending: dict[str, Any] | None = None
        self._answer: asyncio.Future[dict[str, Any]] | None = None
        self._condition = asyncio.Condition()
        self.last_seen: datetime | None = None

    @property
    def connected(self) -> bool:
        return (
            self.last_seen is not None and (datetime.now(UTC) - self.last_seen).total_seconds() < 60
        )

    async def next_command(self) -> dict[str, Any] | None:
        async with self._condition:
            self.last_seen = datetime.now(UTC)
            if self._pending is None:
                try:
                    await asyncio.wait_for(
                        self._condition.wait_for(lambda: self._pending is not None), 20
                    )
                except TimeoutError:
                    return None
            return self._pending

    async def submit(self, command_id: str, answer: dict[str, Any]) -> bool:
        async with self._condition:
            self.last_seen = datetime.now(UTC)
            if self._pending is None or self._pending["id"] != command_id or self._answer is None:
                return False
            if not self._answer.done():
                self._answer.set_result(answer)
            return True

    async def request(
        self, *, url: str, target: str, timeout_seconds: float = 120
    ) -> dict[str, Any]:
        async with self._condition:
            if self._pending is not None:
                raise RuntimeError("browser bridge accepts only one search at a time")
            command = {"id": secrets.token_hex(16), "url": url, "target": target}
            self._pending = command
            self._answer = asyncio.get_running_loop().create_future()
            answer = self._answer
            self._condition.notify_all()
        try:
            return await asyncio.wait_for(answer, timeout_seconds)
        except TimeoutError as exc:
            raise MarketSourceUnavailable("Chrome did not finish the search") from exc
        finally:
            async with self._condition:
                if self._pending is command:
                    self._pending = None
                    self._answer = None
                    self._condition.notify_all()
