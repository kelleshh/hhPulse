import sqlite3
from datetime import date, datetime
from zoneinfo import ZoneInfo

from hhpulse.domain.entities import AnalysisJob, AnalysisScope, CrawlRun, CrawlUnit
from hhpulse.domain.enums import RoleSelectionMode, SearchTarget, UserAgentMode
from hhpulse.domain.value_objects import (
    DailySchedule,
    Methodology,
    RateLimitPolicy,
    SearchQuery,
)
from hhpulse.infrastructure.persistence.database import SqliteDatabase
from hhpulse.infrastructure.persistence.repositories import (
    SqliteAnalysisJobRepository,
    SqliteCrawlExecutionRepository,
)


async def test_job_run_and_units_survive_repository_reconstruction(tmp_path) -> None:
    db_path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(db_path)
    await database.initialize()
    jobs = SqliteAnalysisJobRepository(database)
    executions = SqliteCrawlExecutionRepository(database)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    job = AnalysisJob(
        id="job-1",
        name="Москва — все роли",
        scope=AnalysisScope(
            region_ids=("1",),
            role_selection_mode=RoleSelectionMode.ALL,
        ),
        rate_limit=RateLimitPolicy(max_concurrency=2, max_rps=0.75),
        user_agent_mode=UserAgentMode.PER_WORKER,
        schedule=DailySchedule(),
        methodology=Methodology(),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    await jobs.add(job)
    planned = await executions.get_or_create(
        CrawlRun(id="run-1", job_id=job.id, observation_date=date(2026, 9, 17))
    )
    unit = CrawlUnit(
        id="unit-1",
        run_id=planned.id,
        query=SearchQuery(
            target=SearchTarget.VACANCY,
            observation_date=planned.observation_date,
            region_id="1",
            professional_role_id="96",
        ),
    )
    run = await executions.initialize(planned.start(total_units=1, at=now), (unit,))

    jobs_after_restart = SqliteAnalysisJobRepository(SqliteDatabase(db_path))
    executions_after_restart = SqliteCrawlExecutionRepository(SqliteDatabase(db_path))

    restored_job = await jobs_after_restart.get(job.id)
    restored_run = await executions_after_restart.get(run.id)
    restored_units = await executions_after_restart.list_units(run.id)

    assert restored_job == job
    assert restored_run == run
    assert restored_units == (unit,)


async def test_deleting_job_cascades_to_runs_units_and_events(tmp_path) -> None:
    db_path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(db_path)
    await database.initialize()
    jobs = SqliteAnalysisJobRepository(database)
    executions = SqliteCrawlExecutionRepository(database)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    job = _job(now)
    await jobs.add(job)
    planned = await executions.get_or_create(
        CrawlRun(id="run-delete", job_id=job.id, observation_date=date(2026, 9, 17))
    )
    unit = CrawlUnit(
        id="unit-delete",
        run_id=planned.id,
        query=SearchQuery(
            target=SearchTarget.RESUME,
            observation_date=planned.observation_date,
            region_id="1",
            professional_role_id="96",
        ),
    )
    await executions.initialize(planned.start(total_units=1, at=now), (unit,))

    assert await jobs.delete(job.id) is True
    assert await jobs.get(job.id) is None
    assert await executions.get(planned.id) is None
    assert await executions.list_units(planned.id) == ()

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM crawl_events").fetchone()[0] == 0


async def test_claim_follows_persisted_plan_order_and_does_not_skip_running_unit(
    tmp_path,
) -> None:
    db_path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(db_path)
    await database.initialize()
    jobs = SqliteAnalysisJobRepository(database)
    first = SqliteCrawlExecutionRepository(SqliteDatabase(db_path))
    second = SqliteCrawlExecutionRepository(SqliteDatabase(db_path))
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    job = _job(now)
    await jobs.add(job)
    planned = await first.get_or_create(
        CrawlRun(id="run-1", job_id=job.id, observation_date=date(2026, 9, 17))
    )
    units = tuple(
        CrawlUnit(
            id="z-first-in-plan" if index == 0 else f"a-unit-{index}",
            run_id=planned.id,
            query=SearchQuery(
                target=SearchTarget.VACANCY,
                observation_date=planned.observation_date,
                region_id="1",
                professional_role_id=str(index),
            ),
        )
        for index in range(10)
    )
    await first.initialize(planned.start(total_units=len(units), at=now), units)

    claimed = await first.claim_next_ready(
        planned.id,
        worker_id="worker-1",
        at=now,
    )
    skipped = await second.claim_next_ready(
        planned.id,
        worker_id="worker-2",
        at=now,
    )

    assert claimed is not None
    assert claimed.id == "z-first-in-plan"
    assert skipped is None


async def test_initialize_migrates_iteration_one_crawl_unit_schema(tmp_path) -> None:
    db_path = tmp_path / "hhpulse.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE crawl_units (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                query_json TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                updated_at TEXT,
                last_error TEXT
            )
            """
        )

    await SqliteDatabase(db_path).initialize()

    with sqlite3.connect(db_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(crawl_units)")}
    assert {"retry_at", "worker_id", "plan_position"}.issubset(columns)


async def test_initialize_migrates_existing_jobs_to_safe_sequential_profile(tmp_path) -> None:
    db_path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(db_path)
    await database.initialize()
    jobs = SqliteAnalysisJobRepository(database)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    unsafe = AnalysisJob(
        id="unsafe-job",
        name="Старый профиль",
        scope=AnalysisScope(
            region_ids=("1",),
            role_selection_mode=RoleSelectionMode.ALL,
            include_experience_strata=True,
        ),
        rate_limit=RateLimitPolicy(max_concurrency=8, max_rps=12.0),
        user_agent_mode=UserAgentMode.PER_WORKER,
        schedule=DailySchedule(),
        methodology=Methodology(),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    await jobs.add(unsafe)

    await SqliteDatabase(db_path).initialize()
    migrated = await SqliteAnalysisJobRepository(SqliteDatabase(db_path)).get(unsafe.id)

    assert migrated is not None
    assert migrated.rate_limit == RateLimitPolicy(max_concurrency=1, max_rps=1.0)
    assert migrated.user_agent_mode is UserAgentMode.SHARED
    assert migrated.scope.include_experience_strata is False


def _job(now: datetime) -> AnalysisJob:
    return AnalysisJob(
        id="job-1",
        name="Москва",
        scope=AnalysisScope(
            region_ids=("1",),
            role_selection_mode=RoleSelectionMode.ALL,
        ),
        rate_limit=RateLimitPolicy(max_concurrency=2, max_rps=0.75),
        user_agent_mode=UserAgentMode.PER_WORKER,
        schedule=DailySchedule(),
        methodology=Methodology(),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
