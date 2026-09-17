import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

from hhpulse.domain.entities import AnalysisJob, AnalysisScope, CrawlRun, CrawlUnit
from hhpulse.domain.enums import RoleSelectionMode, RunStatus, SearchTarget, UserAgentMode
from hhpulse.domain.value_objects import (
    DailySchedule,
    FacetGroup,
    FacetOptionCount,
    Methodology,
    ParsedSearchPage,
    RateLimitPolicy,
    SearchObservation,
    SearchQuery,
)
from hhpulse.infrastructure.persistence.database import SqliteDatabase
from hhpulse.infrastructure.persistence.repositories import (
    SqliteAnalysisJobRepository,
    SqliteCrawlExecutionRepository,
)


async def test_completion_and_whole_run_publish_are_atomic(tmp_path) -> None:
    path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(path)
    await database.initialize()
    jobs = SqliteAnalysisJobRepository(database)
    executions = SqliteCrawlExecutionRepository(database)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    job = _job(now)
    await jobs.add(job)
    planned = await executions.get_or_create(
        CrawlRun(id="run-1", job_id=job.id, observation_date=date(2026, 9, 17))
    )
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=planned.observation_date,
        region_id="1",
        professional_role_id="96",
    )
    await executions.initialize(
        planned.start(total_units=1, at=now),
        (CrawlUnit(id="unit-1", run_id=planned.id, query=query),),
    )
    claimed = await executions.claim_next_ready(
        planned.id,
        worker_id="worker-1",
        at=now,
    )
    assert claimed is not None
    completed = await executions.complete_unit(
        claimed.id,
        SearchObservation(query=query, page=_page()),
        at=now,
    )

    assert completed.completed_units == 1
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_observations").fetchone()[0] == 0
        assert (
            connection.execute("SELECT COUNT(*) FROM staged_search_observations").fetchone()[0]
            == 1
        )

    published = await executions.publish_completed(planned.id, at=now)

    assert published.status is RunStatus.SUCCEEDED
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_observations").fetchone()[0] == 1
        assert (
            connection.execute("SELECT COUNT(*) FROM staged_search_observations").fetchone()[0]
            == 0
        )


def _job(now: datetime) -> AnalysisJob:
    return AnalysisJob(
        id="job-1",
        name="Москва",
        scope=AnalysisScope(region_ids=("1",), role_selection_mode=RoleSelectionMode.ALL),
        rate_limit=RateLimitPolicy(),
        user_agent_mode=UserAgentMode.SHARED,
        schedule=DailySchedule(),
        methodology=Methodology(),
        enabled=True,
        created_at=now,
        updated_at=now,
    )


def _page() -> ParsedSearchPage:
    return ParsedSearchPage(
        total_count=123,
        facets=(
            FacetGroup(
                key="label",
                options=(
                    FacetOptionCount(
                        id="low_performance",
                        title="Меньше 10 откликов",
                        count=35,
                    ),
                ),
            ),
        ),
    )
