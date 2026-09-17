from datetime import date

import httpx
import pytest

from hhpulse.domain.enums import SearchTarget, UserAgentMode
from hhpulse.domain.value_objects import RateLimitPolicy, SearchQuery
from hhpulse.infrastructure.hh.client import HhHtmlMarketSource
from hhpulse.infrastructure.hh.errors import HhThrottled
from hhpulse.infrastructure.hh.parser import HhSearchPageParser
from hhpulse.infrastructure.hh.query_builder import HhQueryBuilder
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle
from hhpulse.infrastructure.hh.user_agents import UserAgentProvider


@pytest.mark.asyncio
async def test_http_429_is_classified_as_throttling_and_slows_future_requests() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "7"}, request=request)

    throttle = AdaptiveThrottle(RateLimitPolicy(max_concurrency=1, max_rps=1.0))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = HhHtmlMarketSource(
            http_client=client,
            parser=HhSearchPageParser(),
            query_builder=HhQueryBuilder(),
            throttle=throttle,
            user_agents=UserAgentProvider(UserAgentMode.SHARED),
        )
        query = SearchQuery(
            target=SearchTarget.VACANCY,
            observation_date=date(2026, 9, 17),
            region_id="1",
            professional_role_id="96",
        )

        with pytest.raises(HhThrottled):
            await source.fetch(query)

    assert throttle.snapshot().multiplier >= 7.0
    assert throttle.snapshot().throttled_count == 1
