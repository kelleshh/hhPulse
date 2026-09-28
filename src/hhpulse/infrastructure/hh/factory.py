from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import requests

from hhpulse.application.ports.market_source import MarketSource
from hhpulse.domain.entities import AnalysisJob
from hhpulse.infrastructure.hh.client import HhApiMarketSource
from hhpulse.infrastructure.hh.headers import api_headers
from hhpulse.infrastructure.hh.parser import HhVacancySearchResponseParser
from hhpulse.infrastructure.hh.query_builder import HhApiQueryBuilder
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle


class HhMarketSourceFactory:
    def __init__(
        self,
        *,
        access_token: str,
        user_agent: str,
        timeout_seconds: float = 30.0,
        collect_response_stats: bool = True,
    ) -> None:
        self._access_token = access_token
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._collect_response_stats = collect_response_stats

    @asynccontextmanager
    async def open(self, job: AnalysisJob) -> AsyncIterator[MarketSource]:
        if not self._access_token.strip():
            from hhpulse.infrastructure.hh.errors import HhAccessRejected

            raise HhAccessRejected(
                "HH API access token is missing; set HHPULSE_HH_ACCESS_TOKEN before starting a run"
            )
        session = requests.Session()
        session.headers.update(
            api_headers(access_token=self._access_token, user_agent=self._user_agent)
        )
        try:
            yield HhApiMarketSource(
                session=session,
                timeout_seconds=self._timeout_seconds,
                parser=HhVacancySearchResponseParser(),
                query_builder=HhApiQueryBuilder(),
                role_catalog_parser=HhProfessionalRoleCatalogParser(),
                throttle=AdaptiveThrottle(job.rate_limit),
                collect_response_stats=self._collect_response_stats,
            )
        finally:
            await asyncio.to_thread(session.close)
