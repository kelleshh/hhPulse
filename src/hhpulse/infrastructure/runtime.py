from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4


class AsyncioSleeper:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FileHtmlQuarantine:
    def __init__(
        self,
        directory: str | Path,
        *,
        retention: timedelta = timedelta(hours=24),
        max_document_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        self._directory = Path(directory)
        self._retention = retention
        self._max_document_bytes = max_document_bytes

    async def save(
        self,
        *,
        run_id: str,
        unit_id: str | None,
        html: str,
        observed_at: datetime,
    ) -> str:
        return await asyncio.to_thread(
            self._save_sync,
            run_id,
            unit_id,
            html,
            observed_at,
        )

    async def purge_expired(self, *, now: datetime) -> int:
        return await asyncio.to_thread(self._purge_expired_sync, now)

    def _save_sync(
        self,
        run_id: str,
        unit_id: str | None,
        html: str,
        observed_at: datetime,
    ) -> str:
        payload = html.encode("utf-8")[: self._max_document_bytes]
        self._directory.mkdir(parents=True, exist_ok=True)
        safe_run = self._safe_component(run_id)
        safe_unit = self._safe_component(unit_id or "preflight")
        timestamp = observed_at.strftime("%Y%m%dT%H%M%S%z")
        name = f"{timestamp}_{safe_run}_{safe_unit}_{uuid4().hex}.html"
        path = self._directory / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        observed_timestamp = observed_at.timestamp()
        os.utime(path, (observed_timestamp, observed_timestamp))
        return name

    def _purge_expired_sync(self, now: datetime) -> int:
        if not self._directory.exists():
            return 0
        cutoff = now.timestamp() - self._retention.total_seconds()
        removed = 0
        for path in self._directory.glob("*.html"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    @staticmethod
    def _safe_component(value: str) -> str:
        safe = "".join(character for character in value if character.isalnum() or character in "-_")
        return safe[:80] or "unknown"
