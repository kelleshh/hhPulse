from __future__ import annotations

from email.utils import parsedate_to_datetime
from datetime import UTC, datetime

import httpx

from hhpulse.domain.enums import SearchTarget
from hhpulse.domain.value_objects import ParsedSearchPage, ProfessionalRole, SearchQuery
from hhpulse.infrastructure.hh.errors import HhSourceUnavailable, HhThrottled
from hhpulse.infrastructure.hh.parser import HhSearchPageParser
from hhpulse.infrastructure.hh.query_builder import HhQueryBuilder, HttpParams
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle
from hhpulse.infrastructure.hh.user_agents import UserAgentProvider


class HhHtmlMarketSource:
    VACANCY_URL = "https://hh.ru/search/vacancy"
    RESUME_URL = "https://hh.ru/search/resume"

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        parser: HhSearchPageParser,
        query_builder: HhQueryBuilder,
        throttle: AdaptiveThrottle,
        user_agents: UserAgentProvider,
    ) -> None:
        self._http_client = http_client
        self._parser = parser
        self._query_builder = query_builder
        self._throttle = throttle
        self._user_agents = user_agents

    async def fetch(self, query: SearchQuery, *, worker_index: int = 0) -> ParsedSearchPage:
        url = self.VACANCY_URL if query.target is SearchTarget.VACANCY else self.RESUME_URL
        params = self._query_builder.build(query)
        html = await self._get(url, params=params, worker_index=worker_index)
        return self._parser.parse(html)

    async def discover_roles(self, *, region_id: str) -> tuple[ProfessionalRole, ...]:
        html = await self._get(
            self.VACANCY_URL,
            params=self._query_builder.vacancy_catalog_params(region_id=region_id),
            worker_index=0,
        )
        return self._parser.parse(html).roles()

    async def _get(self, url: str, *, params: HttpParams, worker_index: int) -> str:
        headers = {
            "User-Agent": self._user_agents.for_worker(worker_index),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        }
        async with self._throttle:
            try:
                response = await self._http_client.get(url, params=params, headers=headers)
            except httpx.RequestError as exc:
                raise HhSourceUnavailable(f"HH request failed: {exc}") from exc

        if response.status_code == 429:
            retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
            self._throttle.on_throttled(retry_after_seconds=retry_after)
            raise HhThrottled("HH returned HTTP 429", retry_after_seconds=retry_after)
        if response.status_code in {502, 503, 504}:
            self._throttle.on_throttled()
            raise HhSourceUnavailable(f"HH returned HTTP {response.status_code}")
        if response.status_code == 403 and self._looks_like_challenge(response.text):
            self._throttle.on_throttled()
            raise HhThrottled("HH returned an anti-bot challenge")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HhSourceUnavailable(f"HH returned HTTP {response.status_code}") from exc

        self._throttle.on_success()
        return response.text

    @staticmethod
    def _looks_like_challenge(body: str) -> bool:
        lowered = body.lower()
        return "ddos-guard" in lowered or "js-challenge" in lowered or "captcha" in lowered

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
