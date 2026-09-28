from datetime import UTC, date, datetime

from hhpulse.application.analytics import MarketAnalytics
from hhpulse.application.ports.analytics import PublishedObservation
from hhpulse.domain.enums import SearchTarget
from hhpulse.domain.value_objects import (
    FacetGroup,
    FacetOptionCount,
    ParsedSearchPage,
    QueryFilter,
    SearchObservation,
    SearchQuery,
)


def record(target, role, count, *, filters=(), roles=()):
    day = date(2026, 9, 28)
    page = ParsedSearchPage(
        count,
        (FacetGroup("professional_role", tuple(FacetOptionCount(*item) for item in roles)),)
        if roles
        else (),
    )
    return PublishedObservation(
        observation=SearchObservation(
            query=SearchQuery(target, day, "1", role, extra_filters=filters),
            page=page,
        ),
        published_at=datetime(2026, 9, 28, tzinfo=UTC),
    )


def test_role_counts_and_full_filtered_resume_counts_stay_separate():
    records = [
        record(
            SearchTarget.VACANCY, "*", 100, roles=(("96", "Разработчик", 20), ("160", "DevOps", 10))
        ),
        record(
            SearchTarget.VACANCY,
            "*",
            40,
            filters=(QueryFilter.one("label", "with_salary"),),
            roles=(("96", "Разработчик", 8), ("160", "DevOps", 5)),
        ),
        record(SearchTarget.RESUME, "96", 200),
        record(SearchTarget.RESUME, "160", 70),
        record(
            SearchTarget.RESUME, "96", 80, filters=(QueryFilter.one("label", "only_with_salary"),)
        ),
    ]
    rows = MarketAnalytics._aggregate(records)
    by_role = {row.role_id: row for row in rows}
    assert by_role["96"].vacancies == 20
    assert by_role["96"].resumes == 200
    assert by_role["96"].hh_index == 10
    assert MarketAnalytics._metric(by_role["96"], "salaryVisibleShare") == 0.4
    assert MarketAnalytics._metric(by_role["96"], "resumeSalaryVisibleShare") == 0.4
    assert MarketAnalytics._metric(by_role["160"], "resumeSalaryVisibleShare") is None
