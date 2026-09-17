from datetime import date, datetime
from zoneinfo import ZoneInfo

from hhpulse.domain.entities import AnalysisJob, AnalysisScope, CrawlRun
from hhpulse.domain.enums import RoleSelectionMode, UserAgentMode
from hhpulse.domain.value_objects import DailySchedule, Methodology, RateLimitPolicy
from hhpulse.infrastructure.persistence.database import SqliteDatabase
from hhpulse.infrastructure.persistence.repositories import (
    SqliteAnalysisJobRepository,
    SqliteCrawlRunRepository,
)


async def test_job_and_run_survive_repository_reconstruction(tmp_path) -> None:
    db_path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(db_path)
    await database.initialize()
    jobs = SqliteAnalysisJobRepository(database)
    runs = SqliteCrawlRunRepository(database)
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
    run = CrawlRun(id="run-1", job_id=job.id, observation_date=date(2026, 9, 17)).start(
        total_units=100,
        at=now,
    )
    await runs.add(run)

    # Re-create repository objects as a cheap simulation of process restart.
    jobs_after_restart = SqliteAnalysisJobRepository(SqliteDatabase(db_path))
    runs_after_restart = SqliteCrawlRunRepository(SqliteDatabase(db_path))

    restored_job = await jobs_after_restart.get(job.id)
    restored_run = await runs_after_restart.get(run.id)

    assert restored_job == job
    assert restored_run == run
