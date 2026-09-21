import random
from datetime import date, datetime
from zoneinfo import ZoneInfo

from hhpulse.application.use_cases.planning import BuildDailyCrawlPlan
from hhpulse.domain.entities import AnalysisJob, AnalysisScope
from hhpulse.domain.enums import RoleSelectionMode, SearchTarget, UserAgentMode
from hhpulse.domain.value_objects import (
    DailySchedule,
    Methodology,
    ParsedSearchPage,
    ProfessionalRole,
    RateLimitPolicy,
    SearchQuery,
)


class FakeMarketSource:
    async def fetch(self, query: SearchQuery, *, worker_index: int = 0) -> ParsedSearchPage:
        raise AssertionError("not used by planning")

    async def discover_roles(self, *, region_id: str) -> tuple[ProfessionalRole, ...]:
        assert region_id == "1"
        return (
            ProfessionalRole(id="96", name="Программист, разработчик"),
            ProfessionalRole(id="160", name="DevOps-инженер"),
        )


def _job(*, all_roles: bool, include_experience: bool = True) -> AnalysisJob:
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    return AnalysisJob(
        id="job-1",
        name="Москва",
        scope=AnalysisScope(
            region_ids=("1",),
            role_selection_mode=RoleSelectionMode.ALL if all_roles else RoleSelectionMode.SELECTED,
            role_ids=() if all_roles else ("160",),
            include_experience_strata=include_experience,
        ),
        rate_limit=RateLimitPolicy(),
        user_agent_mode=UserAgentMode.SHARED,
        schedule=DailySchedule(),
        methodology=Methodology(),
        enabled=True,
        created_at=now,
        updated_at=now,
    )


async def test_all_roles_are_discovered_instead_of_hardcoded() -> None:
    plan = await BuildDailyCrawlPlan(
        FakeMarketSource(),
        random_source=random.Random(42),
    ).execute(
        _job(all_roles=True),
        observation_date=date(2026, 9, 17),
    )

    assert {role.id for role in plan.roles} == {"96", "160"}
    # 2 roles * 5 experience strata * 2 sides (vacancy/resume)
    assert len(plan.queries) == 20
    assert {query.target for query in plan.queries} == {SearchTarget.VACANCY, SearchTarget.RESUME}
    assert all(query.target is SearchTarget.RESUME for query in plan.queries[:10])
    assert all(query.target is SearchTarget.VACANCY for query in plan.queries[10:])
    assert {query.professional_role_id for query in plan.queries[:10]} == {"96", "160"}
    assert {query.professional_role_id for query in plan.queries[10:]} == {"96", "160"}


async def test_selected_role_reduces_plan_without_changing_discovery_contract() -> None:
    plan = await BuildDailyCrawlPlan(FakeMarketSource()).execute(
        _job(all_roles=False, include_experience=False),
        observation_date=date(2026, 9, 17),
    )

    assert [role.id for role in plan.roles] == ["160"]
    assert len(plan.queries) == 2
    assert [query.target for query in plan.queries] == [
        SearchTarget.RESUME,
        SearchTarget.VACANCY,
    ]
