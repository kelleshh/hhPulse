from __future__ import annotations

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from hhpulse.domain.entities import AnalysisJob
from hhpulse.domain.value_objects import ParsedSearchPage, ProfessionalRole, SearchQuery


class MarketSource(Protocol):
    async def fetch(self, query: SearchQuery, *, worker_index: int = 0) -> ParsedSearchPage: ...

    async def discover_roles(self, *, region_id: str) -> Sequence[ProfessionalRole]: ...

    async def probe(self, *, region_id: str) -> None: ...


class MarketSourceFactory(Protocol):
    def open(self, job: AnalysisJob) -> AbstractAsyncContextManager[MarketSource]: ...
