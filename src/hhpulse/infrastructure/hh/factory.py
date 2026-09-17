from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from hhpulse.application.ports.market_source import MarketSource
from hhpulse.domain.entities import AnalysisJob
from hhpulse.infrastructure.hh.client import HhHtmlMarketSource
from hhpulse.infrastructure.hh.parser import HhSearchPageParser
from hhpulse.infrastructure.hh.query_builder import HhQueryBuilder
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle
from hhpulse.infrastructure.hh.user_agents import UserAgentProvider


class HhMarketSourceFactory:
    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    @asynccontextmanager
    async def open(self, job: AnalysisJob) -> AsyncIterator[MarketSource]:
        timeout = httpx.Timeout(self._timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            yield HhHtmlMarketSource(
                http_client=client,
                parser=HhSearchPageParser(),
                query_builder=HhQueryBuilder(job.methodology),
                role_catalog_parser=HhProfessionalRoleCatalogParser(),
                throttle=AdaptiveThrottle(job.rate_limit),
                user_agents=UserAgentProvider(job.user_agent_mode),
            )
