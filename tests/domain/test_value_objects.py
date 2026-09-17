from datetime import date

from hhpulse.domain.enums import ExperienceBand
from hhpulse.domain.value_objects import (
    FacetGroup,
    FacetOptionCount,
    MarketSnapshot,
    ParsedSearchPage,
)


def test_hh_index_is_ratio_of_resumes_to_vacancies() -> None:
    vacancy = ParsedSearchPage(total_count=100, facets=(_facet("work_format", "REMOTE", 30),))
    resume = ParsedSearchPage(total_count=450, facets=(_facet("work_format", "REMOTE", 120),))
    snapshot = MarketSnapshot(
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
        experience=ExperienceBand.ANY,
        vacancy=vacancy,
        resume=resume,
        methodology_version="hh-index-daily-v1",
    )

    assert snapshot.hh_index.value == 4.5


def test_hh_index_is_none_when_no_vacancies() -> None:
    vacancy = ParsedSearchPage(total_count=0, facets=(_facet("work_format", "REMOTE", 0),))
    resume = ParsedSearchPage(total_count=10, facets=(_facet("work_format", "REMOTE", 3),))
    snapshot = MarketSnapshot(
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
        experience=ExperienceBand.ANY,
        vacancy=vacancy,
        resume=resume,
        methodology_version="hh-index-daily-v1",
    )

    assert snapshot.hh_index.value is None


def _facet(key: str, option_id: str, count: int) -> FacetGroup:
    return FacetGroup(
        key=key,
        options=(FacetOptionCount(id=option_id, title=option_id, count=count),),
    )
