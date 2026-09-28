from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.value_objects import (
    FacetGroup,
    FacetOptionCount,
    ParsedSearchPage,
    ProfessionalRole,
    SearchQuery,
    VacancyResponseStats,
)
from hhpulse.infrastructure.hh.errors import (
    HhAccessRejected,
    HhParserContractBroken,
    HhSourceUnavailable,
    HhThrottled,
)
from hhpulse.infrastructure.hh.parser import HhVacancySearchResponseParser
from hhpulse.infrastructure.hh.query_builder import HhApiQueryBuilder, HttpParams
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle

_REQUIRED_FACET_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("label", "low_performance", "Меньше 10 откликов"),
    ("label", "with_salary", "Указан доход"),
    ("work_format", "REMOTE", "Удалённо"),
    ("work_format", "HYBRID", "Гибрид"),
    ("education", "higher", "Высшее образование"),
    ("experience", "noExperience", "Нет опыта"),
)


class HhApiMarketSource:
    VACANCIES_URL = "https://api.hh.ru/vacancies"
    PROFESSIONAL_ROLES_URL = "https://api.hh.ru/professional_roles"
    ACTIVE_VACANCY_WINDOW_DAYS = 30
    MAX_SEARCH_DEPTH = 2000
    PAGE_SIZE = 100

    def __init__(
        self,
        *,
        session: requests.Session,
        timeout_seconds: float,
        parser: HhVacancySearchResponseParser,
        query_builder: HhApiQueryBuilder,
        role_catalog_parser: HhProfessionalRoleCatalogParser,
        throttle: AdaptiveThrottle,
        collect_response_stats: bool = True,
    ) -> None:
        self._session = session
        self._timeout_seconds = timeout_seconds
        self._parser = parser
        self._query_builder = query_builder
        self._role_catalog_parser = role_catalog_parser
        self._throttle = throttle
        self._collect_response_stats_enabled = collect_response_stats
        self._role_cache: tuple[ProfessionalRole, ...] | None = None

    async def fetch(self, query: SearchQuery, *, worker_index: int = 0) -> ParsedSearchPage:
        del worker_index
        if query.target is not SearchTarget.VACANCY:
            raise HhAccessRejected(
                "resume collection is not configured in the official HH API adapter"
            )

        raw_payload = await self._get(
            self.VACANCIES_URL,
            params=self._query_builder.build_aggregate(query),
        )
        page = self._parse_search(raw_payload)
        page = await self._complete_required_facets(query, page)
        page = self._inject_selected_role(page, query.professional_role_id)

        if (
            self._collect_response_stats_enabled
            and query.experience is ExperienceBand.ANY
            and page.total_count > 0
        ):
            response_stats = await self._collect_response_stats(query, page.total_count)
            page = replace(page, response_stats=response_stats)
        elif self._collect_response_stats_enabled and page.total_count == 0:
            page = replace(
                page,
                response_stats=VacancyResponseStats.from_counts((), expected_vacancies=0),
            )
        return page

    async def discover_roles(self, *, region_id: str) -> tuple[ProfessionalRole, ...]:
        del region_id
        if self._role_cache is not None:
            return self._role_cache
        payload = await self._get(self.PROFESSIONAL_ROLES_URL, params=())
        try:
            self._role_cache = self._role_catalog_parser.parse(payload)
        except HhParserContractBroken as exc:
            raise HhParserContractBroken(str(exc), raw_payload=payload) from exc
        return self._role_cache

    async def probe(self, *, region_id: str) -> None:
        raw_payload = await self._get(
            self.VACANCIES_URL,
            params=self._query_builder.vacancy_catalog_params(region_id=region_id),
        )
        self._parse_search(raw_payload)

    async def _complete_required_facets(
        self,
        query: SearchQuery,
        page: ParsedSearchPage,
    ) -> ParsedSearchPage:
        facets = {facet.key: list(facet.options) for facet in page.facets}
        for facet_key, option_id, title in _REQUIRED_FACET_OPTIONS:
            if facet_key == "experience" and query.experience is not ExperienceBand.ANY:
                continue
            current = next(
                (option for option in facets.get(facet_key, ()) if option.id == option_id),
                None,
            )
            if current is not None:
                continue
            count = await self._fetch_filtered_count(query, key=facet_key, value=option_id)
            facets.setdefault(facet_key, []).append(
                FacetOptionCount(id=option_id, title=title, count=count)
            )
        return replace(
            page,
            facets=tuple(
                FacetGroup(key=key, options=tuple(options)) for key, options in facets.items()
            ),
        )

    async def _fetch_filtered_count(self, query: SearchQuery, *, key: str, value: str) -> int:
        raw_payload = await self._get(
            self.VACANCIES_URL,
            params=self._query_builder.build_count(query, key=key, value=value),
        )
        payload = self._load_object(raw_payload, context="filtered vacancy count")
        return self._non_negative_int(payload.get("found"), field="found")

    def _inject_selected_role(self, page: ParsedSearchPage, role_id: str) -> ParsedSearchPage:
        role = next(
            (item for item in self._role_cache or () if item.id == role_id),
            None,
        )
        if role is None:
            return page
        role_facet = page.facet("professional_role")
        if role_facet is not None and role_facet.get(role_id) is not None:
            return page
        selected = FacetOptionCount(id=role.id, title=role.name, count=page.total_count)
        facets = list(page.facets)
        if role_facet is None:
            facets.append(FacetGroup(key="professional_role", options=(selected,)))
        else:
            facets = [
                FacetGroup(key=facet.key, options=(*facet.options, selected))
                if facet.key == "professional_role"
                else facet
                for facet in facets
            ]
        return replace(page, facets=tuple(facets))

    async def _collect_response_stats(
        self,
        query: SearchQuery,
        expected_vacancies: int,
    ) -> VacancyResponseStats:
        counts_by_vacancy: dict[str, int] = {}
        if expected_vacancies <= self.MAX_SEARCH_DEPTH:
            await self._collect_interval_pages(
                query,
                counts_by_vacancy,
                date_from=None,
                date_to=None,
            )
        else:
            timezone = ZoneInfo("Europe/Moscow")
            end = datetime.combine(
                query.observation_date + timedelta(days=1),
                time.min,
                tzinfo=timezone,
            ) - timedelta(seconds=1)
            start = datetime.combine(
                query.observation_date - timedelta(days=self.ACTIVE_VACANCY_WINDOW_DAYS - 1),
                time.min,
                tzinfo=timezone,
            )
            await self._collect_interval_recursive(query, counts_by_vacancy, start, end)
        return VacancyResponseStats.from_counts(
            counts_by_vacancy.values(),
            expected_vacancies=expected_vacancies,
        )

    async def _collect_interval_recursive(
        self,
        query: SearchQuery,
        target: dict[str, int],
        date_from: datetime,
        date_to: datetime,
    ) -> None:
        first_payload = await self._response_page_payload(
            query,
            page=0,
            date_from=date_from,
            date_to=date_to,
        )
        found = self._non_negative_int(first_payload.get("found"), field="found")
        if found > self.MAX_SEARCH_DEPTH:
            span_seconds = int((date_to - date_from).total_seconds())
            if span_seconds < 2:
                raise HhParserContractBroken(
                    "HH vacancy search still exceeds 2000 results in a one-second interval"
                )
            midpoint = date_from + timedelta(seconds=span_seconds // 2)
            await self._collect_interval_recursive(
                query,
                target,
                date_from,
                midpoint - timedelta(seconds=1),
            )
            await self._collect_interval_recursive(query, target, midpoint, date_to)
            return
        self._collect_page_items(first_payload, target)
        pages = self._pages(found)
        for page_number in range(1, pages):
            payload = await self._response_page_payload(
                query,
                page=page_number,
                date_from=date_from,
                date_to=date_to,
            )
            self._collect_page_items(payload, target)

    async def _collect_interval_pages(
        self,
        query: SearchQuery,
        target: dict[str, int],
        *,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> None:
        first_payload = await self._response_page_payload(
            query,
            page=0,
            date_from=date_from,
            date_to=date_to,
        )
        found = self._non_negative_int(first_payload.get("found"), field="found")
        if found > self.MAX_SEARCH_DEPTH:
            raise HhParserContractBroken(
                "HH vacancy response-count search exceeded the documented 2000-result depth"
            )
        self._collect_page_items(first_payload, target)
        for page_number in range(1, self._pages(found)):
            payload = await self._response_page_payload(
                query,
                page=page_number,
                date_from=date_from,
                date_to=date_to,
            )
            self._collect_page_items(payload, target)

    async def _response_page_payload(
        self,
        query: SearchQuery,
        *,
        page: int,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> Mapping[str, Any]:
        raw_payload = await self._get(
            self.VACANCIES_URL,
            params=self._query_builder.build_response_page(
                query,
                page=page,
                date_from=date_from,
                date_to=date_to,
            ),
        )
        return self._load_object(raw_payload, context="vacancy response-count page")

    @classmethod
    def _collect_page_items(cls, payload: Mapping[str, Any], target: dict[str, int]) -> None:
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            raise HhParserContractBroken("HH vacancy response-count page has no items list")
        for raw_item in raw_items:
            if not isinstance(raw_item, Mapping):
                raise HhParserContractBroken("HH vacancy item is not an object")
            vacancy_id = str(raw_item.get("id", "")).strip()
            counters = raw_item.get("counters")
            if not vacancy_id or not isinstance(counters, Mapping):
                raise HhParserContractBroken(
                    "HH vacancy item is missing id/counters with responses_count_enabled=true"
                )
            responses = cls._non_negative_int(counters.get("responses"), field="counters.responses")
            target[vacancy_id] = responses

    @classmethod
    def _load_object(cls, raw_payload: str, *, context: str) -> Mapping[str, Any]:
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise HhParserContractBroken(f"cannot decode HH {context} JSON: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise HhParserContractBroken(f"HH {context} payload is not an object")
        return payload

    def _parse_search(self, raw_payload: str) -> ParsedSearchPage:
        try:
            return self._parser.parse(raw_payload)
        except HhParserContractBroken as exc:
            raise HhParserContractBroken(str(exc), raw_payload=raw_payload) from exc

    async def _get(self, url: str, *, params: HttpParams) -> str:
        async with self._throttle:
            try:
                response = await asyncio.to_thread(
                    self._session.get,
                    url,
                    params=params,
                    timeout=self._timeout_seconds,
                )
            except requests.RequestException as exc:
                self._throttle.on_unavailable()
                raise HhSourceUnavailable(f"HH API request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise HhAccessRejected(
                f"HH API rejected authorization with HTTP {response.status_code}: "
                f"{self._error_description(response.text)}"
            )
        if response.status_code == 429:
            retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
            self._throttle.on_throttled(retry_after_seconds=retry_after)
            raise HhThrottled("HH API returned HTTP 429", retry_after_seconds=retry_after)
        if response.status_code in {502, 503, 504}:
            self._throttle.on_unavailable()
            raise HhSourceUnavailable(f"HH API returned HTTP {response.status_code}")
        if response.status_code == 400:
            raise HhParserContractBroken(
                f"HH API rejected generated query with HTTP 400: "
                f"{self._error_description(response.text)}",
                raw_payload=response.text,
            )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise HhSourceUnavailable(f"HH API returned HTTP {response.status_code}") from exc

        self._throttle.on_success()
        return response.text

    @staticmethod
    def _error_description(raw_payload: str) -> str:
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return raw_payload[:300].replace("\n", " ")
        if isinstance(payload, Mapping):
            description = payload.get("description") or payload.get("oauth_error")
            if description:
                return str(description)
            errors = payload.get("errors")
            if errors:
                return json.dumps(errors, ensure_ascii=False)[:300]
        return raw_payload[:300].replace("\n", " ")

    @staticmethod
    def _pages(found: int) -> int:
        return math.ceil(found / HhApiMarketSource.PAGE_SIZE) if found else 0

    @staticmethod
    def _non_negative_int(value: Any, *, field: str) -> int:
        if isinstance(value, bool):
            raise HhParserContractBroken(f"HH field {field!r} must be an integer")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise HhParserContractBroken(f"HH field {field!r} must be an integer") from exc
        if number < 0:
            raise HhParserContractBroken(f"HH field {field!r} must not be negative")
        return number

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        if value is None:
            return None
        stripped = value.strip()
        try:
            return max(0.0, float(stripped))
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
