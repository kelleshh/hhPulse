from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from hhpulse.application.errors import (
    MarketSourceThrottled,
    MarketSourceUnavailable,
    ParserContractBroken,
)
from hhpulse.application.use_cases.execution import (
    ExecuteDailyCrawl,
    PrepareOrResumeDailyRun,
    RunCrawlWorkerPool,
)
from hhpulse.domain.entities import AnalysisJob, AnalysisScope
from hhpulse.domain.enums import RoleSelectionMode, RunStatus, RunUnitStatus, UserAgentMode
from hhpulse.domain.errors import InvalidStateTransition
from hhpulse.domain.value_objects import (
    DailySchedule,
    FacetGroup,
    FacetOptionCount,
    Methodology,
    ParsedSearchPage,
    ProfessionalRole,
    RateLimitPolicy,
    RetryPolicy,
    SearchObservation,
    SearchQuery,
)
from hhpulse.infrastructure.persistence.database import SqliteDatabase
from hhpulse.infrastructure.persistence.repositories import (
    SqliteAnalysisJobRepository,
    SqliteCrawlExecutionRepository,
)

MOSCOW = ZoneInfo("Europe/Moscow")


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


class AdvancingSleeper:
    def __init__(self, clock: MutableClock) -> None:
        self.clock = clock
        self.calls: list[float] = []

    async def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)
        self.clock.advance(seconds)
        await asyncio.sleep(0)


class MemoryQuarantine:
    def __init__(self) -> None:
        self.documents: list[str] = []

    async def save(self, **kwargs: object) -> str:
        self.documents.append(str(kwargs["html"]))
        return "diagnostic.html"

    async def purge_expired(self, *, now: datetime) -> int:
        return 0


class FakeSource:
    def __init__(self, outcomes: list[object] | None = None) -> None:
        self.outcomes = outcomes or []
        self.probes = 0
        self.fetches: list[SearchQuery] = []

    async def probe(self, *, region_id: str) -> None:
        assert region_id == "1"
        self.probes += 1
        self._raise_next_if_error(probe=True)

    async def discover_roles(self, *, region_id: str) -> tuple[ProfessionalRole, ...]:
        assert region_id == "1"
        return (ProfessionalRole(id="96", name="Программист"),)

    async def fetch(
        self,
        query: SearchQuery,
        *,
        worker_index: int = 0,
    ) -> ParsedSearchPage:
        self.fetches.append(query)
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            if isinstance(outcome, ParsedSearchPage):
                return outcome
        return _page()

    def _raise_next_if_error(self, *, probe: bool) -> None:
        if probe and self.outcomes and isinstance(self.outcomes[0], ProbeFailure):
            failure = self.outcomes.pop(0)
            raise failure.error


class OfflineFetchSource(FakeSource):
    async def fetch(
        self,
        query: SearchQuery,
        *,
        worker_index: int = 0,
    ) -> ParsedSearchPage:
        self.fetches.append(query)
        raise MarketSourceUnavailable("connection unavailable")


class ProbeFailure:
    def __init__(self, error: Exception) -> None:
        self.error = error


class FakeSourceFactory:
    def __init__(self, source: FakeSource) -> None:
        self.source = source

    @asynccontextmanager
    async def open(self, job: AnalysisJob) -> AsyncIterator[FakeSource]:
        yield self.source


async def test_daily_executor_runs_preflight_and_atomically_publishes_all_units(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW))
    repository, jobs, db_path = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=4, include_experience=True)
    await jobs.add(job)
    source = FakeSource()

    run = await _executor(repository, source, clock).execute(job, clock.today())

    assert run.status is RunStatus.SUCCEEDED
    assert run.total_units == 10
    assert run.completed_units == 10
    assert source.probes == 3
    assert len(source.fetches) == 10
    assert len(set(source.fetches)) == 10
    progress = await repository.progress(run.id)
    assert progress.total_attempts == 10
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_observations").fetchone()[0] == 10
        assert (
            connection.execute("SELECT COUNT(*) FROM staged_search_observations").fetchone()[0]
            == 0
        )


async def test_429_persists_retry_and_resumes_without_repeating_successful_units(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW))
    repository, jobs, _ = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=1, include_experience=False)
    await jobs.add(job)
    source = FakeSource(
        outcomes=[MarketSourceThrottled("HTTP 429", retry_after_seconds=7.0)]
    )
    sleeper = AdvancingSleeper(clock)

    run = await _executor(repository, source, clock, sleeper=sleeper).execute(job, clock.today())

    assert run.status is RunStatus.SUCCEEDED
    assert run.total_units == 2
    assert len(source.fetches) == 3
    assert (clock.now() - datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW)).total_seconds() >= 7
    progress = await repository.progress(run.id)
    assert progress.total_attempts == 3


async def test_parser_contract_break_quarantines_html_and_aborts_whole_run(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW))
    repository, jobs, db_path = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=1, include_experience=False)
    await jobs.add(job)
    source = FakeSource(
        outcomes=[ParserContractBroken("missing searchClusters", raw_html="<html>broken</html>")]
    )
    quarantine = MemoryQuarantine()

    run = await _executor(repository, source, clock, quarantine=quarantine).execute(
        job,
        clock.today(),
    )

    assert run.status is RunStatus.PARSER_BROKEN
    assert run.error_code == "PARSER_CONTRACT_BROKEN"
    assert quarantine.documents == ["<html>broken</html>"]
    assert all(unit.status is RunUnitStatus.FAILED for unit in await repository.list_units(run.id))
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_observations").fetchone()[0] == 0


async def test_restart_recovers_claimed_unit_and_finishes_from_persisted_state(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW))
    repository, jobs, db_path = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=1, include_experience=False)
    await jobs.add(job)
    source = FakeSource()
    prepare = PrepareOrResumeDailyRun(repository, preflight_successes=1)
    run = await prepare.execute(
        job,
        observation_date=clock.today(),
        source=source,
        at=clock.now(),
    )
    claimed = await repository.claim_next_ready(
        run.id,
        worker_id="dead-worker",
        at=clock.now(),
    )
    assert claimed is not None

    restarted_repository = SqliteCrawlExecutionRepository(SqliteDatabase(db_path))
    resumed = await PrepareOrResumeDailyRun(
        restarted_repository,
        preflight_successes=1,
    ).execute(
        job,
        observation_date=clock.today(),
        source=source,
        at=clock.now(),
    )
    recovered_units = await restarted_repository.list_units(run.id)

    assert resumed.status is RunStatus.WAITING_SOURCE
    assert sum(unit.status is RunUnitStatus.WAITING_RETRY for unit in recovered_units) == 1
    workers = RunCrawlWorkerPool(
        restarted_repository,
        MemoryQuarantine(),
        clock,
        AdvancingSleeper(clock),
        RetryPolicy(initial_delay_seconds=1, max_delay_seconds=5),
    )
    result = await workers.execute(
        job,
        resumed,
        source,
        deadline=datetime(2026, 9, 18, 0, 0, tzinfo=MOSCOW),
    )
    assert result.status is RunStatus.SUCCEEDED
    assert result.completed_units == result.total_units == 2


async def test_unavailable_source_until_midnight_expires_planned_run(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 23, 59, 50, tzinfo=MOSCOW))
    repository, jobs, _ = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=1, include_experience=False)
    await jobs.add(job)
    failure = ProbeFailure(MarketSourceUnavailable("offline"))
    source = FakeSource(outcomes=[failure, failure, failure])
    sleeper = AdvancingSleeper(clock)

    run = await _executor(
        repository,
        source,
        clock,
        sleeper=sleeper,
        retry_policy=RetryPolicy(initial_delay_seconds=5, max_delay_seconds=5),
    ).execute(job, clock.today())

    assert run.status is RunStatus.EXPIRED
    assert run.total_units == 0
    assert run.error_code == "DAY_EXPIRED"


async def test_unavailable_source_during_crawl_retries_until_midnight_then_expires(
    tmp_path,
) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 23, 59, 50, tzinfo=MOSCOW))
    repository, jobs, db_path = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=1, include_experience=False)
    await jobs.add(job)
    source = OfflineFetchSource()

    run = await _executor(
        repository,
        source,
        clock,
        retry_policy=RetryPolicy(initial_delay_seconds=5, max_delay_seconds=5),
    ).execute(job, clock.today())

    assert run.status is RunStatus.EXPIRED
    assert run.total_units == 2
    assert run.completed_units == 0
    assert len(source.fetches) >= 2
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_observations").fetchone()[0] == 0


async def test_parser_break_during_preflight_creates_red_terminal_run(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW))
    repository, jobs, _ = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=1, include_experience=False)
    await jobs.add(job)
    source = FakeSource(
        outcomes=[
            ProbeFailure(
                ParserContractBroken("catalog contract changed", raw_html="<html>changed</html>")
            )
        ]
    )
    quarantine = MemoryQuarantine()

    run = await _executor(repository, source, clock, quarantine=quarantine).execute(
        job,
        clock.today(),
    )

    assert run.status is RunStatus.PARSER_BROKEN
    assert run.total_units == 0
    assert quarantine.documents == ["<html>changed</html>"]


async def test_missing_staged_row_rolls_back_publish_state_transition(tmp_path) -> None:
    clock = MutableClock(datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW))
    repository, jobs, db_path = await _repositories(tmp_path)
    job = _job(clock.now(), max_concurrency=1, include_experience=False)
    await jobs.add(job)
    source = FakeSource()
    run = await PrepareOrResumeDailyRun(repository, preflight_successes=1).execute(
        job,
        observation_date=clock.today(),
        source=source,
        at=clock.now(),
    )
    for _ in range(run.total_units):
        unit = await repository.claim_next_ready(run.id, worker_id="worker-1", at=clock.now())
        assert unit is not None
        await repository.complete_unit(
            unit.id,
            SearchObservation(query=unit.query, page=_page()),
            at=clock.now(),
        )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            DELETE FROM staged_search_observations
            WHERE unit_id = (SELECT unit_id FROM staged_search_observations LIMIT 1)
            """
        )
        connection.commit()

    with pytest.raises(InvalidStateTransition, match="staging"):
        await repository.publish_completed(run.id, at=clock.now())

    restored = await repository.get(run.id)
    assert restored is not None
    assert restored.status is RunStatus.RUNNING


async def _repositories(tmp_path):
    db_path = tmp_path / "hhpulse.sqlite3"
    database = SqliteDatabase(db_path)
    await database.initialize()
    return (
        SqliteCrawlExecutionRepository(database),
        SqliteAnalysisJobRepository(database),
        db_path,
    )


def _job(
    now: datetime,
    *,
    max_concurrency: int,
    include_experience: bool,
) -> AnalysisJob:
    return AnalysisJob(
        id="job-1",
        name="Москва",
        scope=AnalysisScope(
            region_ids=("1",),
            role_selection_mode=RoleSelectionMode.ALL,
            include_experience_strata=include_experience,
        ),
        rate_limit=RateLimitPolicy(max_concurrency=max_concurrency, max_rps=20),
        user_agent_mode=UserAgentMode.SHARED,
        schedule=DailySchedule(),
        methodology=Methodology(),
        enabled=True,
        created_at=now,
        updated_at=now,
    )


def _executor(
    repository: SqliteCrawlExecutionRepository,
    source: FakeSource,
    clock: MutableClock,
    *,
    sleeper: AdvancingSleeper | None = None,
    quarantine: MemoryQuarantine | None = None,
    retry_policy: RetryPolicy | None = None,
) -> ExecuteDailyCrawl:
    resolved_sleeper = sleeper or AdvancingSleeper(clock)
    return ExecuteDailyCrawl(
        repository,
        FakeSourceFactory(source),
        quarantine or MemoryQuarantine(),
        clock,
        resolved_sleeper,
        retry_policy or RetryPolicy(initial_delay_seconds=1, max_delay_seconds=10),
        preflight_successes=3,
    )


def _page() -> ParsedSearchPage:
    return ParsedSearchPage(
        total_count=100,
        facets=(
            FacetGroup(
                key="experience",
                options=(
                    FacetOptionCount(id="noExperience", title="Нет опыта", count=25),
                ),
            ),
        ),
    )
