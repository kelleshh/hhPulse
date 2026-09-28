import json
from datetime import date

import pytest
import requests

from hhpulse.domain.enums import SearchTarget
from hhpulse.domain.value_objects import RateLimitPolicy, SearchQuery
from hhpulse.infrastructure.hh.client import HhApiMarketSource
from hhpulse.infrastructure.hh.errors import HhAccessRejected, HhThrottled
from hhpulse.infrastructure.hh.parser import HhVacancySearchResponseParser
from hhpulse.infrastructure.hh.query_builder import HhApiQueryBuilder
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
    payload: object | None = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    body = text if text is not None else json.dumps(payload or {}, ensure_ascii=False)
    response._content = body.encode("utf-8")
    response.encoding = "utf-8"
    response.headers.update(headers or {})
    response.url = "https://api.hh.ru/test"
    return response


async def _no_sleep(_: float) -> None:
    return None


def _source(
    session: StubSession,
    *,
    collect_response_stats: bool = False,
) -> tuple[HhApiMarketSource, AdaptiveThrottle]:
    throttle = AdaptiveThrottle(
        RateLimitPolicy(max_concurrency=1, max_rps=1.0),
        sleeper=_no_sleep,
    )
    return (
        HhApiMarketSource(
            session=session,  # type: ignore[arg-type]
            timeout_seconds=30.0,
            parser=HhVacancySearchResponseParser(),
            query_builder=HhApiQueryBuilder(),
            role_catalog_parser=HhProfessionalRoleCatalogParser(),
            throttle=throttle,
            collect_response_stats=collect_response_stats,
        ),
        throttle,
    )


def _aggregate_payload(*, found: int = 3) -> dict[str, object]:
    def item(group: str, value: str, name: str, count: int) -> dict[str, object]:
        return {
            "name": name,
            "url": f"https://api.hh.ru/vacancies?{group}={value}&area=1",
            "count": count,
        }

    return {
        "found": found,
        "items": [],
        "clusters": [
            {
                "id": "label",
                "items": [
                    item("label", "low_performance", "Меньше 10 откликов", min(found, 2)),
                    item("label", "with_salary", "Указан доход", min(found, 2)),
                ],
            },
            {
                "id": "work_format",
                "items": [
                    item("work_format", "REMOTE", "Удалённо", min(found, 1)),
                    item("work_format", "HYBRID", "Гибрид", min(found, 1)),
                ],
            },
            {
                "id": "education",
                "items": [item("education", "higher", "Высшее", min(found, 1))],
            },
            {
                "id": "experience",
                "items": [item("experience", "noExperience", "Нет опыта", min(found, 1))],
            },
        ],
    }


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

    assert throttle.snapshot().multiplier >= 7.0
    assert throttle.snapshot().throttled_count == 1


@pytest.mark.asyncio
async def test_role_discovery_uses_full_official_catalog_and_caches_it() -> None:
    payload = {
        "categories": [
            {"roles": [{"id": "96", "name": "Программист"}]},
            {"roles": [{"id": "96", "name": "Программист"}]},
            {"roles": [{"id": "160", "name": "DevOps-инженер"}]},
        ]
    }
    session = StubSession([_response(200, payload=payload)])
    source, _ = _source(session)

    first = await source.discover_roles(region_id="1")
    second = await source.discover_roles(region_id="2")

    assert {role.id for role in first} == {"96", "160"}
    assert second == first
    assert len(session.calls) == 1


@pytest.mark.asyncio
async def test_403_is_terminal_authorization_error_not_html_parser_failure() -> None:
    source, _ = _source(
        StubSession(
            [
                _response(
                    403,
                    payload={"description": "Forbidden", "errors": [{"type": "oauth"}]},
                )
            ]
        )
    )
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    with pytest.raises(HhAccessRejected, match="403"):
        await source.fetch(query)


@pytest.mark.asyncio
async def test_response_counts_are_compressed_to_histogram() -> None:
    aggregate = _aggregate_payload(found=3)
    page = {
        "found": 3,
        "page": 0,
        "pages": 1,
        "per_page": 100,
        "items": [
            {"id": "a", "counters": {"responses": 0}},
            {"id": "b", "counters": {"responses": 7}},
            {"id": "c", "counters": {"responses": 7}},
        ],
    }
    source, _ = _source(
        StubSession([_response(200, payload=aggregate), _response(200, payload=page)]),
        collect_response_stats=True,
    )
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    result = await source.fetch(query)

    assert result.response_stats is not None
    assert result.response_stats.complete is True
    assert result.response_stats.mean == pytest.approx(14 / 3)
    assert result.response_stats.median == 7.0
    assert [(item.responses, item.vacancies) for item in result.response_stats.histogram] == [
        (0, 1),
        (7, 2),
    ]
