import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

from hhpulse.domain.entities import AnalysisJob, AnalysisScope, CrawlRun, CrawlUnit
from hhpulse.domain.enums import RoleSelectionMode, SearchTarget, UserAgentMode
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
    SqliteCrawlRunRepository,
    SqliteCrawlUnitRepository,
    SqliteObservationRepository,
)


async def test_staging_is_not_visible_as_published_until_whole_run_succeeds(tmp_path) -> None:
    path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(path)
    await database.initialize()
    jobs = SqliteAnalysisJobRepository(database)
    runs = SqliteCrawlRunRepository(database)
    units = SqliteCrawlUnitRepository(database)
    observations = SqliteObservationRepository(database)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))

    job = AnalysisJob(
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
    await jobs.add(job)
    run = CrawlRun(id="run-1", job_id=job.id, observation_date=date(2026, 9, 17)).start(
        total_units=1,
        at=now,
    )
    await runs.add(run)
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )
    unit = CrawlUnit(id="unit-1", run_id=run.id, query=query).start_attempt(at=now)
    await units.add_many((unit,))
    page = ParsedSearchPage(
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
    await observations.stage(run.id, unit.id, SearchObservation(query=query, page=page))

    with sqlite3.connect(path) as connection:
        published_count = connection.execute(
            "SELECT COUNT(*) FROM search_observations"
        ).fetchone()[0]
        staged_count = connection.execute(
            "SELECT COUNT(*) FROM staged_search_observations"
        ).fetchone()[0]
        assert published_count == 0
        assert staged_count == 1

    unit = unit.succeed(at=now)
    await units.update(unit)
    run = run.mark_unit_completed().succeed(at=now)
    await runs.update(run)
    await observations.publish_run(run.id)

    with sqlite3.connect(path) as connection:
        published_count = connection.execute(
            "SELECT COUNT(*) FROM search_observations"
        ).fetchone()[0]
        staged_count = connection.execute(
            "SELECT COUNT(*) FROM staged_search_observations"
        ).fetchone()[0]
        assert published_count == 1
        assert staged_count == 0
