from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import requests

from hhpulse.application.ports.market_source import MarketSource
from hhpulse.domain.entities import AnalysisJob
from hhpulse.infrastructure.hh.client import HhHtmlMarketSource
from hhpulse.infrastructure.hh.parser import HhSearchPageParser
from hhpulse.infrastructure.hh.query_builder import HhQueryBuilder
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle
from hhpulse.infrastructure.hh.user_agents import DEFAULT_HEADERS


class HhMarketSourceFactory:
    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self._timeout_seconds = timeout_seconds

    @asynccontextmanager
    async def open(self, job: AnalysisJob) -> AsyncIterator[MarketSource]:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        try:
            yield HhHtmlMarketSource(
                session=session,
                timeout_seconds=self._timeout_seconds,
                parser=HhSearchPageParser(),
                query_builder=HhQueryBuilder(job.methodology),
                role_catalog_parser=HhProfessionalRoleCatalogParser(),
                throttle=AdaptiveThrottle(job.rate_limit),
            )
        finally:
            await asyncio.to_thread(session.close)
