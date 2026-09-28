from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

from hhpulse.application.errors import (
    BrowserUnavailable,
    MarketSourceRejected,
    MarketSourceUnavailable,
    ParserContractBroken,
)
from hhpulse.application.ports.catalog import ProfessionalRoleCatalog
from hhpulse.application.ports.market_source import MarketSource
from hhpulse.domain.entities import AnalysisJob
from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.value_objects import (
    FacetGroup,
    FacetOptionCount,
    ParsedSearchPage,
    ProfessionalRole,
    SearchQuery,
)
from hhpulse.infrastructure.browser.bridge import BrowserBridge


def search_url(query: SearchQuery) -> str:
    remote = query.region_id == "remote"
    area = "113" if remote else query.region_id
    if query.target is SearchTarget.VACANCY:
        params: list[tuple[str, str]] = [
            ("area", area),
            ("no_magic", "true"),
            ("ored_clusters", "true"),
        ]
        if query.professional_role_id != "*":
            params.append(("professional_role", query.professional_role_id))
    else:
        start = query.observation_date - timedelta(days=59)
        params = [
            ("logic", "normal"),
            ("pos", "full_text"),
            ("exp_period", "all_time"),
            ("filter_exp_period", "all_time"),
            ("area", area),
            ("relocation", "living_or_relocation"),
            ("job_search_status", "active_search"),
            ("job_search_status", "looking_for_offers"),
            ("job_search_status", "unknown"),
            ("gender", "unknown"),
            ("order_by", "relevance"),
            ("search_period", "-1"),
            ("date_from", start.strftime("%d.%m.%Y")),
            ("date_to", query.observation_date.strftime("%d.%m.%Y")),
            ("items_on_page", "20"),
            ("no_magic", "true"),
            ("text", ""),
            ("professional_role", query.professional_role_id),
        ]
    if query.experience is not ExperienceBand.ANY:
        params.append(("experience", query.experience.value))
    if remote:
        params.append(("work_format", "REMOTE"))
    for flt in query.extra_filters:
        if remote and flt.key == "work_format":
            if flt.values != ("REMOTE",):
                raise ValueError("remote region cannot combine another work format")
            continue
        params.extend((flt.key, value) for value in flt.values)
    path = "vacancy" if query.target is SearchTarget.VACANCY else "resume"
    return f"https://hh.ru/search/{path}?{urlencode(params)}"


class BrowserMarketSource:
    def __init__(
        self, bridge: BrowserBridge, catalog: ProfessionalRoleCatalog, job: AnalysisJob
    ) -> None:
        self._bridge = bridge
        self._catalog = catalog
        self._job = job
        self._roles: tuple[ProfessionalRole, ...] = ()
        self._next_at = 0.0

    async def probe(self, *, region_id: str) -> None:
        if not self._bridge.connected:
            raise BrowserUnavailable(
                "Open the hhPulse Chrome companion tab in the signed-in Chrome"
            )

    async def discover_roles(self, *, region_id: str) -> Sequence[ProfessionalRole]:
        self._roles = await self._catalog.list_roles()
        return self._roles

    async def fetch(self, query: SearchQuery, *, worker_index: int = 0) -> ParsedSearchPage:
        if not self._roles:
            await self.discover_roles(region_id=query.region_id)
        if not self._bridge.connected:
            raise BrowserUnavailable("Chrome companion is not connected")
        loop = asyncio.get_running_loop()
        await asyncio.sleep(max(0.0, self._next_at - loop.time()))
        expected_url = search_url(query)
        try:
            result = await self._bridge.request(
                url=expected_url,
                target=query.target.value,
                timeout_seconds=240 if query.target is SearchTarget.VACANCY else 120,
            )
        finally:
            self._next_at = loop.time() + 2.0 + random.uniform(0.0, 2.0)
        status = result.get("status")
        if status in {"blocked", "auth"}:
            raise MarketSourceRejected(
                f"HH browser search stopped: {status}; {result.get('reason', '')}"
            )
        if status == "unavailable":
            raise MarketSourceUnavailable(
                str(result.get("reason", "browser temporarily unavailable"))
            )
        if status != "ok":
            raise ParserContractBroken(
                f"Chrome search extraction failed: {result.get('reason', status)}"
            )
        self._validate_url(expected_url, str(result.get("url", "")))
        total = self._number(result.get("total"), "total")
        if query.target is SearchTarget.RESUME:
            visible = result.get("visible")
            hidden = result.get("hidden")
            if visible is None or hidden is None:
                raise ParserContractBroken("resume visible or hidden count is missing")
            if total != self._number(visible, "visible") + self._number(hidden, "hidden"):
                raise ParserContractBroken(
                    "resume full count differs from visible + hidden for this search"
                )
            role = next((r for r in self._roles if r.id == query.professional_role_id), None)
            if role is None:
                raise ParserContractBroken("searched resume role is absent from the role catalog")
            facet = FacetGroup("professional_role", (FacetOptionCount(role.id, role.name, total),))
            return ParsedSearchPage(
                total_count=total,
                facets=(facet,),
                methodology_version="hh-browser-complete-count-v1",
            )

        if result.get("tree_complete") is not True:
            raise ParserContractBroken(
                "vacancy profession tree was not fully expanded and traversed"
            )
        raw_roles = result.get("roles")
        if not isinstance(raw_roles, list):
            raise ParserContractBroken("vacancy tree has no role counts")
        observed: dict[str, FacetOptionCount] = {}
        for item in raw_roles:
            if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
                raise ParserContractBroken("invalid vacancy profession entry")
            role_id = str(item["id"])
            option = FacetOptionCount(
                role_id,
                str(item.get("name", "")).strip(),
                self._number(item.get("count"), "role count"),
            )
            if role_id in observed and observed[role_id] != option:
                raise ParserContractBroken(f"conflicting vacancy count for profession {role_id}")
            observed[role_id] = option
        if total > 0 and not observed:
            raise ParserContractBroken("vacancy tree contains no professions")
        known_ids = {role.id for role in self._roles}
        if not self._job.scope.role_ids and observed.keys() - known_ids:
            raise ParserContractBroken("vacancy tree has new role IDs absent from the catalog")
        for role in self._roles:
            observed.setdefault(role.id, FacetOptionCount(role.id, role.name, 0))
        selected = (
            set(self._job.scope.role_ids)
            if self._job.scope.role_ids
            else {r.id for r in self._roles}
        )
        options = tuple(observed[role_id] for role_id in sorted(selected) if role_id in observed)
        if len(options) != len(selected):
            raise ParserContractBroken("selected professions missing from the vacancy tree/catalog")
        return ParsedSearchPage(
            total_count=total,
            facets=(FacetGroup("professional_role", options),),
            methodology_version="hh-browser-complete-count-v1",
        )

    @staticmethod
    def _number(value: object, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ParserContractBroken(f"{label} must be a non-negative integer")
        return value

    @staticmethod
    def _validate_url(expected: str, actual: str) -> None:
        expected_parts = urlsplit(expected)
        actual_parts = urlsplit(actual)
        if (
            actual_parts.hostname not in {"hh.ru", "www.hh.ru"}
            or expected_parts.path != actual_parts.path
        ):
            raise ParserContractBroken("Chrome displayed a different search page")
        expected_params = parse_qs(expected_parts.query, keep_blank_values=True)
        actual_params = parse_qs(actual_parts.query, keep_blank_values=True)
        for key, values in expected_params.items():
            if sorted(values) != sorted(actual_params.get(key, [])):
                raise ParserContractBroken(f"Chrome search filters changed: {key}")


class BrowserMarketSourceFactory:
    def __init__(self, bridge: BrowserBridge, catalog: ProfessionalRoleCatalog) -> None:
        self._bridge = bridge
        self._catalog = catalog

    @asynccontextmanager
    async def open(self, job: AnalysisJob) -> AsyncIterator[MarketSource]:
        yield BrowserMarketSource(self._bridge, self._catalog, job)
