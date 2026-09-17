from __future__ import annotations

from typing import Protocol, Sequence

from hhpulse.domain.value_objects import ParsedSearchPage, ProfessionalRole, SearchQuery


class MarketSource(Protocol):
    async def fetch(self, query: SearchQuery, *, worker_index: int = 0) -> ParsedSearchPage: ...

    async def discover_roles(self, *, region_id: str) -> Sequence[ProfessionalRole]: ...
