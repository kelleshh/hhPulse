from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests

from hhpulse.domain.enums import SearchTarget
from hhpulse.domain.value_objects import ParsedSearchPage, ProfessionalRole, SearchQuery
from hhpulse.infrastructure.hh.errors import (
    HhParserContractBroken,
    HhSourceUnavailable,
    HhThrottled,
)
from hhpulse.infrastructure.hh.parser import HhSearchPageParser
from hhpulse.infrastructure.hh.query_builder import HhQueryBuilder, HttpParams
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle


class HhHtmlMarketSource:
    VACANCY_URL = "https://hh.ru/search/vacancy"
    RESUME_URL = "https://hh.ru/search/resume"
    PROFESSIONAL_ROLES_URL = "https://api.hh.ru/professional_roles"

    def __init__(
        self,
        *,
        session: requests.Session,
        timeout_seconds: float,
        parser: HhSearchPageParser,
        query_builder: HhQueryBuilder,
        role_catalog_parser: HhProfessionalRoleCatalogParser,
        throttle: AdaptiveThrottle,
    ) -> None:
        self._session = session
        self._timeout_seconds = timeout_seconds
        self._parser = parser
        self._query_builder = query_builder
        self._role_catalog_parser = role_catalog_parser
        self._throttle = throttle
        self._role_cache: tuple[ProfessionalRole, ...] | None = None

    async def fetch(self, query: SearchQuery, *, worker_index: int = 0) -> ParsedSearchPage:
        url = self.VACANCY_URL if query.target is SearchTarget.VACANCY else self.RESUME_URL
        params = self._query_builder.build(query)
        html = await self._get(url, params=params, worker_index=worker_index)
        return self._parse(html)

    async def discover_roles(self, *, region_id: str) -> tuple[ProfessionalRole, ...]:
        del region_id
        if self._role_cache is not None:
            return self._role_cache
        payload = await self._get(
            self.PROFESSIONAL_ROLES_URL,
            params=(),
            worker_index=0,
        )
        try:
            self._role_cache = self._role_catalog_parser.parse(payload)
        except HhParserContractBroken as exc:
            raise HhParserContractBroken(str(exc), raw_html=payload) from exc
        return self._role_cache

    async def probe(self, *, region_id: str) -> None:
        html = await self._get(
            self.VACANCY_URL,
            params=self._query_builder.vacancy_catalog_params(region_id=region_id),
            worker_index=0,
        )
        self._parse(html)

    async def _get(self, url: str, *, params: HttpParams, worker_index: int) -> str:
        del worker_index
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
                await self._throttle.wait_after_response()
                raise HhSourceUnavailable(f"HH request failed: {exc}") from exc
            await self._throttle.wait_after_response()

        if self._looks_like_hard_block(response.text):
            raise HhParserContractBroken(
                "HH returned an anti-bot/WAF block page; the whole run was stopped",
                raw_html=response.text,
            )
        if response.status_code == 403:
            raise HhParserContractBroken(
                "HH refused the request with HTTP 403; the whole run was stopped",
                raw_html=response.text,
            )
        if response.status_code == 429:
            retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
            self._throttle.on_throttled(retry_after_seconds=retry_after)
            raise HhThrottled("HH returned HTTP 429", retry_after_seconds=retry_after)
        if response.status_code in {502, 503, 504}:
            self._throttle.on_unavailable()
            raise HhSourceUnavailable(f"HH returned HTTP {response.status_code}")
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise HhSourceUnavailable(f"HH returned HTTP {response.status_code}") from exc

        self._throttle.on_success()
        return response.text

    def _parse(self, raw_html: str) -> ParsedSearchPage:
        try:
            return self._parser.parse(raw_html)
        except HhParserContractBroken as exc:
            raise HhParserContractBroken(str(exc), raw_html=raw_html) from exc

    @staticmethod
    def _looks_like_hard_block(body: str) -> bool:
        lowered = body.lower()
        markers = (
            "ddos-guard",
            "js-challenge",
            "captcha",
            "malicious activity blocked",
            "waf@hh.ru",
        )
        return any(marker in lowered for marker in markers)

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        if value is None:
            return None
        stripped = value.strip()
        if stripped.isdigit():
            return float(stripped)
        try:
            retry_at = parsedate_to_datetime(stripped)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
