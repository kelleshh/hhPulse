from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import date, datetime, time, timedelta
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from hhpulse.application.errors import MarketSourceUnavailable, ParserContractBroken
from hhpulse.application.ports.clock import Clock
from hhpulse.application.ports.market_source import MarketSource, MarketSourceFactory
from hhpulse.application.ports.repositories import CrawlExecutionRepository
from hhpulse.application.ports.runtime import HtmlQuarantine, Sleeper
from hhpulse.application.use_cases.planning import BuildDailyCrawlPlan
from hhpulse.domain.entities import AnalysisJob, CrawlRun, CrawlUnit
from hhpulse.domain.enums import RunStatus
from hhpulse.domain.errors import InvalidStateTransition
from hhpulse.domain.value_objects import RetryPolicy, SearchObservation, SearchQuery

TERMINAL_RUN_STATUSES = {
    RunStatus.PARSER_BROKEN,
    RunStatus.FAILED,
    RunStatus.EXPIRED,
    RunStatus.SUCCEEDED,
}


class PrepareOrResumeDailyRun:
    def __init__(
        self,
        executions: CrawlExecutionRepository,
        *,
        preflight_successes: int = 3,
    ) -> None:
        if preflight_successes < 1:
            raise ValueError("preflight_successes must be positive")
        self._executions = executions
        self._preflight_successes = preflight_successes

    async def execute(
        self,
        job: AnalysisJob,
        *,
        observation_date: date,
        source: MarketSource,
        at: datetime,
    ) -> CrawlRun:
        candidate = CrawlRun(
            id=self._run_id(job.id, observation_date),
            job_id=job.id,
            observation_date=observation_date,
        )
        run = await self._executions.get_or_create(candidate)
        if run.status in TERMINAL_RUN_STATUSES:
            return run
        if run.status is not RunStatus.PLANNED:
            await self._executions.recover_interrupted(run.id, at=at)
            refreshed = await self._executions.get(run.id)
            if refreshed is None:
                raise RuntimeError(f"crawl run {run.id!r} disappeared during recovery")
            return refreshed

        await self._preflight(job, source)
        plan = await BuildDailyCrawlPlan(source).execute(job, observation_date=observation_date)
        units = tuple(
            CrawlUnit(
                id=self._unit_id(run.id, query),
                run_id=run.id,
                query=query,
            )
            for query in plan.queries
        )
        started = run.start(total_units=len(units), at=at)
        return await self._executions.initialize(started, units)

    async def _preflight(self, job: AnalysisJob, source: MarketSource) -> None:
        region_id = sorted(job.scope.region_ids)[0]
        for _ in range(self._preflight_successes):
            await source.probe(region_id=region_id)

    @staticmethod
    def _run_id(job_id: str, observation_date: date) -> str:
        key = f"hhpulse:run:{job_id}:{observation_date.isoformat()}"
        return str(uuid5(NAMESPACE_URL, key))

    @staticmethod
    def _unit_id(run_id: str, query: SearchQuery) -> str:
        filters = ";".join(
            f"{item.key}={','.join(item.values)}"
            for item in sorted(query.extra_filters, key=lambda x: x.key)
        )
        key = "|".join(
            (
                run_id,
                query.target.value,
                query.observation_date.isoformat(),
                query.region_id,
                query.professional_role_id,
                query.experience.value,
                filters,
            )
        )
        return str(uuid5(NAMESPACE_URL, key))


class AbortRunOnParserContract:
    def __init__(
        self,
        executions: CrawlExecutionRepository,
        quarantine: HtmlQuarantine,
        clock: Clock,
    ) -> None:
        self._executions = executions
        self._quarantine = quarantine
        self._clock = clock

    async def execute(
        self,
        run_id: str,
        *,
        unit_id: str | None,
        error: ParserContractBroken,
    ) -> CrawlRun:
        at = self._clock.now()
        reference = await self._save_diagnostic(run_id, unit_id, error, at)
        suffix = f"; diagnostic={reference}" if reference else ""
        return await self._executions.abort_parser(
            run_id,
            message=f"{error}{suffix}",
            at=at,
        )

    async def _save_diagnostic(
        self,
        run_id: str,
        unit_id: str | None,
        error: ParserContractBroken,
        at: datetime,
    ) -> str | None:
        if error.raw_html is None:
            return None
        try:
            return await self._quarantine.save(
                run_id=run_id,
                unit_id=unit_id,
                html=error.raw_html,
                observed_at=at,
            )
        except Exception as quarantine_error:
            return f"quarantine failed: {quarantine_error}"


class RunCrawlWorkerPool:
    def __init__(
        self,
        executions: CrawlExecutionRepository,
        quarantine: HtmlQuarantine,
        clock: Clock,
        sleeper: Sleeper,
        retry_policy: RetryPolicy,
        *,
        idle_poll_seconds: float = 1.0,
    ) -> None:
        self._executions = executions
        self._quarantine = quarantine
        self._clock = clock
        self._sleeper = sleeper
        self._retry_policy = retry_policy
        self._idle_poll_seconds = idle_poll_seconds
        self._parser_abort = AbortRunOnParserContract(executions, quarantine, clock)

    async def execute(
        self,
        job: AnalysisJob,
        run: CrawlRun,
        source: MarketSource,
        *,
        deadline: datetime,
    ) -> CrawlRun:
        stopped = asyncio.Event()
        async with asyncio.TaskGroup() as group:
            for worker_index in range(job.rate_limit.max_concurrency):
                group.create_task(
                    self._worker(
                        run.id,
                        source,
                        worker_index=worker_index,
                        deadline=deadline,
                        stopped=stopped,
                    )
                )
        refreshed = await self._executions.get(run.id)
        if refreshed is None:
            raise RuntimeError(f"crawl run {run.id!r} disappeared after worker execution")
        return refreshed

    async def _worker(
        self,
        run_id: str,
        source: MarketSource,
        *,
        worker_index: int,
        deadline: datetime,
        stopped: asyncio.Event,
    ) -> None:
        worker_id = f"worker-{worker_index + 1}"
        while not stopped.is_set() and self._clock.now() < deadline:
            unit = await self._claim(run_id, worker_id)
            if unit is None:
                if await self._publish_if_complete(run_id, stopped):
                    return
                await self._wait_for_ready_unit(run_id, deadline)
                continue
            if not await self._fetch_one(unit, source, worker_index, stopped):
                return

    async def _claim(self, run_id: str, worker_id: str) -> CrawlUnit | None:
        try:
            return await self._executions.claim_next_ready(
                run_id,
                worker_id=worker_id,
                at=self._clock.now(),
            )
        except InvalidStateTransition:
            return None

    async def _fetch_one(
        self,
        unit: CrawlUnit,
        source: MarketSource,
        worker_index: int,
        stopped: asyncio.Event,
    ) -> bool:
        try:
            page = await source.fetch(unit.query, worker_index=worker_index)
        except ParserContractBroken as exc:
            with suppress(InvalidStateTransition):
                await self._parser_abort.execute(unit.run_id, unit_id=unit.id, error=exc)
            stopped.set()
            return False
        except MarketSourceUnavailable as exc:
            await self._defer(unit, exc)
            return True
        except Exception as exc:
            await self._fail_unexpected(unit.run_id, exc)
            stopped.set()
            return False

        try:
            await self._executions.complete_unit(
                unit.id,
                SearchObservation(query=unit.query, page=page),
                at=self._clock.now(),
            )
        except InvalidStateTransition:
            return False
        return True

    async def _defer(self, unit: CrawlUnit, error: MarketSourceUnavailable) -> None:
        at = self._clock.now()
        delay = self._retry_policy.delay_seconds(
            attempts=unit.attempts,
            retry_after_seconds=error.retry_after_seconds,
        )
        try:
            await self._executions.defer_unit(
                unit.id,
                error=str(error),
                retry_at=at + timedelta(seconds=delay),
                at=at,
            )
        except InvalidStateTransition:
            return

    async def _fail_unexpected(self, run_id: str, error: Exception) -> None:
        try:
            await self._executions.fail_run(
                run_id,
                code="UNEXPECTED_CRAWL_ERROR",
                message=f"{type(error).__name__}: {error}",
                at=self._clock.now(),
            )
        except InvalidStateTransition:
            return

    async def _publish_if_complete(self, run_id: str, stopped: asyncio.Event) -> bool:
        run = await self._executions.get(run_id)
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            stopped.set()
            return True
        if run.total_units > 0 and run.completed_units == run.total_units:
            await self._executions.publish_completed(run_id, at=self._clock.now())
            stopped.set()
            return True
        return False

    async def _wait_for_ready_unit(self, run_id: str, deadline: datetime) -> None:
        progress = await self._executions.progress(run_id)
        now = self._clock.now()
        wake_at = progress.next_retry_at or (now + timedelta(seconds=self._idle_poll_seconds))
        seconds = min(
            self._idle_poll_seconds,
            max(0.0, (wake_at - now).total_seconds()),
            max(0.0, (deadline - now).total_seconds()),
        )
        await self._sleeper.sleep(max(0.01, seconds))


class ExecuteDailyCrawl:
    def __init__(
        self,
        executions: CrawlExecutionRepository,
        source_factory: MarketSourceFactory,
        quarantine: HtmlQuarantine,
        clock: Clock,
        sleeper: Sleeper,
        retry_policy: RetryPolicy,
        *,
        preflight_successes: int = 3,
    ) -> None:
        self._executions = executions
        self._source_factory = source_factory
        self._quarantine = quarantine
        self._clock = clock
        self._sleeper = sleeper
        self._retry_policy = retry_policy
        self._parser_abort = AbortRunOnParserContract(executions, quarantine, clock)
        self._prepare = PrepareOrResumeDailyRun(
            executions,
            preflight_successes=preflight_successes,
        )
        self._workers = RunCrawlWorkerPool(
            executions,
            quarantine,
            clock,
            sleeper,
            retry_policy,
        )

    async def execute(self, job: AnalysisJob, observation_date: date) -> CrawlRun:
        deadline = self._deadline(observation_date, job.schedule.timezone)
        planning_failures = 0
        await self._quarantine.purge_expired(now=self._clock.now())
        async with self._source_factory.open(job) as source:
            while self._clock.now() < deadline:
                try:
                    run = await self._prepare.execute(
                        job,
                        observation_date=observation_date,
                        source=source,
                        at=self._clock.now(),
                    )
                except ParserContractBroken as exc:
                    return await self._abort_planned_run(job, observation_date, exc)
                except MarketSourceUnavailable as exc:
                    planning_failures += 1
                    await self._wait_for_source(exc, planning_failures, deadline)
                    continue
                except Exception as exc:
                    return await self._fail_planned_run(job, observation_date, exc)

                if run.status in TERMINAL_RUN_STATUSES:
                    return run
                result = await self._workers.execute(
                    job,
                    run,
                    source,
                    deadline=deadline,
                )
                if result.status not in TERMINAL_RUN_STATUSES and self._clock.now() >= deadline:
                    return await self._executions.expire_run(result.id, at=self._clock.now())
                return result

        return await self._expire(job, observation_date)

    async def _wait_for_source(
        self,
        error: MarketSourceUnavailable,
        attempts: int,
        deadline: datetime,
    ) -> None:
        delay = self._retry_policy.delay_seconds(
            attempts=attempts,
            retry_after_seconds=error.retry_after_seconds,
        )
        remaining = max(0.0, (deadline - self._clock.now()).total_seconds())
        await self._sleeper.sleep(min(delay, remaining))

    async def _abort_planned_run(
        self,
        job: AnalysisJob,
        observation_date: date,
        error: ParserContractBroken,
    ) -> CrawlRun:
        run = await self._require_daily_run(job.id, observation_date)
        return await self._parser_abort.execute(run.id, unit_id=None, error=error)

    async def _fail_planned_run(
        self,
        job: AnalysisJob,
        observation_date: date,
        error: Exception,
    ) -> CrawlRun:
        run = await self._require_daily_run(job.id, observation_date)
        return await self._executions.fail_run(
            run.id,
            code="CRAWL_PLAN_ERROR",
            message=f"{type(error).__name__}: {error}",
            at=self._clock.now(),
        )

    async def _expire(self, job: AnalysisJob, observation_date: date) -> CrawlRun:
        run = await self._require_daily_run(job.id, observation_date)
        if run.status in TERMINAL_RUN_STATUSES:
            return run
        return await self._executions.expire_run(run.id, at=self._clock.now())

    async def _require_daily_run(self, job_id: str, observation_date: date) -> CrawlRun:
        run = await self._executions.get_for_job_date(job_id, observation_date)
        if run is None:
            candidate = CrawlRun(
                id=PrepareOrResumeDailyRun._run_id(job_id, observation_date),
                job_id=job_id,
                observation_date=observation_date,
            )
            return await self._executions.get_or_create(candidate)
        return run

    async def _require_run(self, run_id: str) -> CrawlRun:
        run = await self._executions.get(run_id)
        if run is None:
            raise RuntimeError(f"crawl run {run_id!r} disappeared")
        return run

    @staticmethod
    def _deadline(observation_date: date, timezone: str) -> datetime:
        next_day = observation_date + timedelta(days=1)
        return datetime.combine(next_day, time.min, tzinfo=ZoneInfo(timezone))
