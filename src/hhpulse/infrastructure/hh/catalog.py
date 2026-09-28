from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import requests

from hhpulse.application.ports.catalog import ProfessionalRoleCatalog
from hhpulse.domain.value_objects import ProfessionalRole
from hhpulse.infrastructure.hh.headers import api_headers
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.role_snapshot import ROLE_SNAPSHOT


class HhProfessionalRoleCatalog(ProfessionalRoleCatalog):
    URL = "https://api.hh.ru/professional_roles"

    def __init__(
        self,
        *,
        access_token: str = "",
        user_agent: str = "hhPulse/0.4 (configure-HHPULSE_HH_USER_AGENT)",
        timeout_seconds: float = 30.0,
        ttl: timedelta = timedelta(hours=12),
    ) -> None:
        self._access_token = access_token
        self._user_agent = user_agent
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
            except requests.RequestException:
                if self._cached:
                    return self._cached
                self._cached = tuple(
                    ProfessionalRole(id=role_id, name=name) for role_id, name in ROLE_SNAPSHOT
                )
                self._cached_at = now
                return self._cached

            roles = self._parser.parse(response.text)
            self._cached = tuple(sorted(roles, key=lambda role: role.name.casefold()))
            self._cached_at = now
            return self._cached

    def _fetch(self) -> requests.Response:
        with requests.Session() as session:
            session.headers.update(
                api_headers(access_token=self._access_token, user_agent=self._user_agent)
            )
            response = session.get(self.URL, timeout=self._timeout_seconds)
            response.raise_for_status()
            return response
