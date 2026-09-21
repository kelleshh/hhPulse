import json
import random
from datetime import date

import pytest
import requests

from hhpulse.domain.enums import SearchTarget
from hhpulse.domain.value_objects import RateLimitPolicy, SearchQuery
from hhpulse.infrastructure.hh.client import HhHtmlMarketSource
from hhpulse.infrastructure.hh.errors import HhParserContractBroken, HhThrottled
from hhpulse.infrastructure.hh.parser import HhSearchPageParser
from hhpulse.infrastructure.hh.query_builder import HhQueryBuilder
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser
from hhpulse.infrastructure.hh.throttle import AdaptiveThrottle


class StubSession:
    def __init__(self, responses: list[requests.Response]) -> None:
        self._responses = responses
        self.calls: list[tuple[str, object, float]] = []

    def get(self, url: str, *, params: object, timeout: float) -> requests.Response:
        self.calls.append((url, params, timeout))
        return self._responses.pop(0)


def _response(
    status_code: int,
    *,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response._content = text.encode("utf-8")
    response.encoding = "utf-8"
    response.headers.update(headers or {})
    response.url = "https://hh.ru/test"
    return response


async def _no_sleep(_: float) -> None:
    return None


def _source(session: StubSession) -> tuple[HhHtmlMarketSource, AdaptiveThrottle]:
    throttle = AdaptiveThrottle(
        RateLimitPolicy(max_concurrency=1, max_rps=1.0),
        sleeper=_no_sleep,
    )
    return (
        HhHtmlMarketSource(
            session=session,  # type: ignore[arg-type]
            timeout_seconds=30.0,
            parser=HhSearchPageParser(),
            query_builder=HhQueryBuilder(),
            role_catalog_parser=HhProfessionalRoleCatalogParser(),
            throttle=throttle,
        ),
        throttle,
    )


@pytest.mark.asyncio
async def test_http_429_is_classified_as_throttling_and_slows_future_requests() -> None:
    source, throttle = _source(
        StubSession([_response(429, headers={"Retry-After": "7"})])
    )
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    with pytest.raises(HhThrottled):
        await source.fetch(query)

    assert throttle.snapshot().multiplier >= 7.0 / 1.35
    assert throttle.snapshot().throttled_count == 1


@pytest.mark.asyncio
async def test_role_discovery_uses_full_official_catalog_and_caches_it() -> None:
    payload = json.dumps(
        {
            "categories": [
                {"roles": [{"id": "96", "name": "Программист"}]},
                {"roles": [{"id": "96", "name": "Программист"}]},
                {"roles": [{"id": "160", "name": "DevOps-инженер"}]},
            ]
        },
        ensure_ascii=False,
    )
    session = StubSession([_response(200, text=payload)])
    source, _ = _source(session)

    first = await source.discover_roles(region_id="1")
    second = await source.discover_roles(region_id="2")

    assert {role.id for role in first} == {"96", "160"}
    assert second == first
    assert len(session.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [200, 403])
async def test_waf_page_is_terminal_and_preserved_for_diagnostics(status_code: int) -> None:
    body = "<html><h1>Malicious activity blocked</h1><p>waf@hh.ru</p></html>"
    source, _ = _source(StubSession([_response(status_code, text=body)]))
    query = SearchQuery(
        target=SearchTarget.RESUME,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    with pytest.raises(HhParserContractBroken) as captured:
        await source.fetch(query)

    assert captured.value.raw_html == body


@pytest.mark.asyncio
async def test_every_received_response_is_followed_by_requested_random_delay() -> None:
    recorded_delays: list[float] = []

    async def record_delay(seconds: float) -> None:
        recorded_delays.append(seconds)

    throttle = AdaptiveThrottle(
        RateLimitPolicy(),
        random_source=random.Random(42),
        sleeper=record_delay,
    )
    session = StubSession([_response(429)])
    source = HhHtmlMarketSource(
        session=session,  # type: ignore[arg-type]
        timeout_seconds=30.0,
        parser=HhSearchPageParser(),
        query_builder=HhQueryBuilder(),
        role_catalog_parser=HhProfessionalRoleCatalogParser(),
        throttle=throttle,
    )
    query = SearchQuery(
        target=SearchTarget.RESUME,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    with pytest.raises(HhThrottled):
        await source.fetch(query)

    assert len(recorded_delays) == 1
    assert 0.9 <= recorded_delays[0] <= 1.8
