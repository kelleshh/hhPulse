from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import requests

from hhpulse.application.ports.catalog import ProfessionalRoleCatalog
from hhpulse.domain.value_objects import ProfessionalRole
from hhpulse.infrastructure.hh.errors import HhSourceUnavailable
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.user_agents import DEFAULT_HEADERS


class HhProfessionalRoleCatalog(ProfessionalRoleCatalog):
    URL = "https://api.hh.ru/professional_roles"

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        ttl: timedelta = timedelta(hours=12),
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._ttl = ttl
        self._parser = HhProfessionalRoleCatalogParser()
        self._cached: tuple[ProfessionalRole, ...] = ()
        self._cached_at: datetime | None = None
        self._lock = asyncio.Lock()

    async def list_roles(self) -> tuple[ProfessionalRole, ...]:
        now = datetime.now(UTC)
        if self._cached_at is not None and now - self._cached_at < self._ttl:
            return self._cached

        async with self._lock:
            now = datetime.now(UTC)
            if self._cached_at is not None and now - self._cached_at < self._ttl:
                return self._cached
            try:
                response = await asyncio.to_thread(self._fetch)
            except requests.RequestException as exc:
                if self._cached:
                    return self._cached
                raise HhSourceUnavailable(f"HH role catalog request failed: {exc}") from exc

            roles = self._parser.parse(response.text)
            self._cached = tuple(sorted(roles, key=lambda role: role.name.casefold()))
            self._cached_at = now
            return self._cached

    def _fetch(self) -> requests.Response:
        with requests.Session() as session:
            session.headers.update(DEFAULT_HEADERS)
            response = session.get(self.URL, timeout=self._timeout_seconds)
            response.raise_for_status()
            return response
