from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, date, datetime

from hhpulse.application.ports.repositories import (
    AnalysisJobRepository,
    CrawlEvent,
    CrawlExecutionRepository,
    CrawlProgress,
)
from hhpulse.domain.entities import AnalysisJob, AnalysisScope, CrawlRun, CrawlUnit
from hhpulse.domain.enums import RoleSelectionMode, RunStatus, RunUnitStatus, UserAgentMode
from hhpulse.domain.errors import InvalidStateTransition
from hhpulse.domain.value_objects import (
    DailySchedule,
    Methodology,
    RateLimitPolicy,
    SearchObservation,
)
from hhpulse.infrastructure.persistence.codec import (
    observation_to_json,
    query_from_json,
    query_to_json,
)
from hhpulse.infrastructure.persistence.database import SqliteDatabase


class SqliteAnalysisJobRepository(AnalysisJobRepository):
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    async def add(self, job: AnalysisJob) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO analysis_jobs (
                    id, name, region_ids_json, role_selection_mode, role_ids_json,
                    include_experience_strata, max_concurrency, max_rps, user_agent_mode,
                    timezone, methodology_version, active_resume_window_days, enabled,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(job),
            )

        await self._database.write(operation)

    async def get(self, job_id: str) -> AnalysisJob | None:
        def operation(connection: sqlite3.Connection) -> AnalysisJob | None:
            row = connection.execute(
                "SELECT * FROM analysis_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            return self._from_row(row) if row is not None else None

        return await self._database.read(operation)

    async def list(self) -> Sequence[AnalysisJob]:
        def operation(connection: sqlite3.Connection) -> tuple[AnalysisJob, ...]:
            rows = connection.execute(
                "SELECT * FROM analysis_jobs ORDER BY created_at, id"
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)

        return await self._database.read(operation)

    async def update(self, job: AnalysisJob) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            cursor = connection.execute(
                """
                UPDATE analysis_jobs SET
                    name = ?, region_ids_json = ?, role_selection_mode = ?, role_ids_json = ?,
                    include_experience_strata = ?, max_concurrency = ?, max_rps = ?,
                    user_agent_mode = ?, timezone = ?, methodology_version = ?,
                    active_resume_window_days = ?, enabled = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (*self._to_row(job)[1:], job.id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"analysis job {job.id!r} does not exist")

        await self._database.write(operation)

    @staticmethod
    def _to_row(job: AnalysisJob) -> tuple[object, ...]:
        return (
            job.id,
            job.name,
            json.dumps(job.scope.region_ids, ensure_ascii=False),
            job.scope.role_selection_mode.value,
            json.dumps(job.scope.role_ids, ensure_ascii=False),
            int(job.scope.include_experience_strata),
            job.rate_limit.max_concurrency,
            job.rate_limit.max_rps,
            job.user_agent_mode.value,
            job.schedule.timezone,
            job.methodology.version,
            job.methodology.active_resume_window_days,
            int(job.enabled),
            job.created_at.isoformat(),
            job.updated_at.isoformat(),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> AnalysisJob:
        return AnalysisJob(
            id=str(row["id"]),
            name=str(row["name"]),
            scope=AnalysisScope(
                region_ids=tuple(json.loads(str(row["region_ids_json"]))),
                role_selection_mode=RoleSelectionMode(str(row["role_selection_mode"])),
                role_ids=tuple(json.loads(str(row["role_ids_json"]))),
                include_experience_strata=bool(row["include_experience_strata"]),
            ),
            rate_limit=RateLimitPolicy(
                max_concurrency=int(row["max_concurrency"]),
                max_rps=float(row["max_rps"]),
            ),
            user_agent_mode=UserAgentMode(str(row["user_agent_mode"])),
            schedule=DailySchedule(timezone=str(row["timezone"])),
            methodology=Methodology(
                version=str(row["methodology_version"]),
                active_resume_window_days=int(row["active_resume_window_days"]),
            ),
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )


class SqliteCrawlExecutionRepository(CrawlExecutionRepository):
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    async def get_or_create(self, run: CrawlRun) -> CrawlRun:
        if run.status is not RunStatus.PLANNED:
            raise ValueError("get_or_create accepts only a planned run")

        def operation(connection: sqlite3.Connection) -> CrawlRun:
            connection.execute(
                """
                INSERT OR IGNORE INTO crawl_runs (
                    id, job_id, observation_date, status, total_units, completed_units,
                    started_at, finished_at, error_code, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._run_to_row(run),
            )
            row = connection.execute(
                "SELECT * FROM crawl_runs WHERE job_id = ? AND observation_date = ?",
                (run.job_id, run.observation_date.isoformat()),
            ).fetchone()
            if row is None:
                raise RuntimeError("failed to create or load daily crawl run")
            return self._run_from_row(row)

        return await self._database.write(operation)

    async def get(self, run_id: str) -> CrawlRun | None:
        def operation(connection: sqlite3.Connection) -> CrawlRun | None:
            row = connection.execute(
                "SELECT * FROM crawl_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            return self._run_from_row(row) if row is not None else None

        return await self._database.read(operation)

    async def get_for_job_date(
        self,
        job_id: str,
        observation_date: date,
    ) -> CrawlRun | None:
        def operation(connection: sqlite3.Connection) -> CrawlRun | None:
            row = connection.execute(
                "SELECT * FROM crawl_runs WHERE job_id = ? AND observation_date = ?",
                (job_id, observation_date.isoformat()),
            ).fetchone()
            return self._run_from_row(row) if row is not None else None

        return await self._database.read(operation)

    async def initialize(self, run: CrawlRun, units: Sequence[CrawlUnit]) -> CrawlRun:
        if run.status is not RunStatus.RUNNING or run.total_units != len(units):
            raise ValueError("initialized run must be running and match its unit count")
        if any(unit.run_id != run.id for unit in units):
            raise ValueError("every crawl unit must belong to the initialized run")

        def operation(connection: sqlite3.Connection) -> CrawlRun:
            current = self._require_run(connection, run.id)
            if current.status is not RunStatus.PLANNED:
                return current
            unit_count = self._unit_count(connection, run.id)
            if unit_count:
                raise RuntimeError("planned run unexpectedly already contains crawl units")
            self._update_run(connection, run)
            connection.executemany(
                """
                INSERT INTO crawl_units (
                    id, run_id, query_json, status, attempts, updated_at, last_error,
                    retry_at, worker_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._unit_to_row(unit) for unit in units],
            )
            self._append_event(
                connection,
                run_id=run.id,
                unit_id=None,
                at=run.started_at,
                level="info",
                event_type="run_started",
                message=f"План сбора создан: {run.total_units} запросов",
            )
            return run

        return await self._database.write(operation)

    async def recover_interrupted(self, run_id: str, *, at: datetime) -> int:
        def operation(connection: sqlite3.Connection) -> int:
            run = self._require_active_run(connection, run_id)
            rows = connection.execute(
                "SELECT * FROM crawl_units WHERE run_id = ? AND status = ?",
                (run_id, RunUnitStatus.RUNNING.value),
            ).fetchall()
            for row in rows:
                recovered = self._unit_from_row(row).recover_interrupted(at=at)
                self._update_unit(connection, recovered)
            if rows and run.status is RunStatus.RUNNING:
                self._update_run(connection, run.wait_for_source())
            if rows:
                self._append_event(
                    connection,
                    run_id=run_id,
                    unit_id=None,
                    at=at,
                    level="warning",
                    event_type="workers_recovered",
                    message=f"После перезапуска восстановлено обработчиков: {len(rows)}",
                )
            return len(rows)

        return await self._database.write(operation)

    async def claim_next_ready(
        self,
        run_id: str,
        *,
        worker_id: str,
        at: datetime,
    ) -> CrawlUnit | None:
        if not worker_id.strip():
            raise ValueError("worker id must not be empty")

        def operation(connection: sqlite3.Connection) -> CrawlUnit | None:
            run = self._require_active_run(connection, run_id)
            row = connection.execute(
                """
                UPDATE crawl_units SET
                    status = ?, attempts = attempts + 1, updated_at = ?,
                    last_error = NULL, retry_at = NULL, worker_id = ?
                WHERE id = (
                    SELECT id FROM crawl_units
                    WHERE run_id = ? AND (
                        status = ? OR (status = ? AND (retry_at IS NULL OR retry_at <= ?))
                    )
                    ORDER BY id
                    LIMIT 1
                )
                RETURNING *
                """,
                (
                    RunUnitStatus.RUNNING.value,
                    self._datetime_to_db(at),
                    worker_id,
                    run_id,
                    RunUnitStatus.PENDING.value,
                    RunUnitStatus.WAITING_RETRY.value,
                    self._datetime_to_db(at),
                ),
            ).fetchone()
            if row is None:
                return None
            claimed = self._unit_from_row(row)
            if run.status is RunStatus.WAITING_SOURCE:
                self._update_run(connection, run.resume())
            self._append_event(
                connection,
                run_id=run_id,
                unit_id=claimed.id,
                at=at,
                level="info",
                event_type="unit_started",
                message=self._query_message(claimed, prefix=f"{worker_id}: запрос"),
            )
            return claimed

        return await self._database.write(operation)

    async def defer_unit(
        self,
        unit_id: str,
        *,
        error: str,
        retry_at: datetime,
        at: datetime,
    ) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            unit = self._require_unit(connection, unit_id)
            run = self._require_active_run(connection, unit.run_id)
            deferred = unit.wait_retry(error=error, retry_at=retry_at, at=at)
            self._update_unit(connection, deferred)
            if run.status is RunStatus.RUNNING:
                self._update_run(connection, run.wait_for_source())
            self._append_event(
                connection,
                run_id=unit.run_id,
                unit_id=unit.id,
                at=at,
                level="warning",
                event_type="retry_scheduled",
                message=f"Повтор в {retry_at.isoformat()}: {error}",
            )

        await self._database.write(operation)

    async def complete_unit(
        self,
        unit_id: str,
        observation: SearchObservation,
        *,
        at: datetime,
    ) -> CrawlRun:
        def operation(connection: sqlite3.Connection) -> CrawlRun:
            unit = self._require_unit(connection, unit_id)
            run = self._require_active_run(connection, unit.run_id)
            if observation.query != unit.query:
                raise ValueError("observation query does not match the claimed crawl unit")
            completed_unit = unit.succeed(at=at)
            completed_run = run.mark_unit_completed()
            connection.execute(
                """
                INSERT INTO staged_search_observations (run_id, unit_id, observation_json)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id, unit_id) DO UPDATE SET
                    observation_json = excluded.observation_json
                """,
                (run.id, unit.id, observation_to_json(observation)),
            )
            self._update_unit(connection, completed_unit)
            self._update_run(connection, completed_run)
            self._append_event(
                connection,
                run_id=run.id,
                unit_id=unit.id,
                at=at,
                level="success",
                event_type="unit_completed",
                message=self._query_message(
                    unit,
                    prefix=f"Получено {observation.page.total_count}",
                ),
            )
            return completed_run

        return await self._database.write(operation)

    async def abort_parser(
        self,
        run_id: str,
        *,
        message: str,
        at: datetime,
    ) -> CrawlRun:
        def operation(connection: sqlite3.Connection) -> CrawlRun:
            run = self._require_run(connection, run_id)
            broken = run.parser_broken(message=message, at=at)
            self._cancel_incomplete_units(connection, run_id, message, at)
            self._update_run(connection, broken)
            self._append_event(
                connection,
                run_id=run_id,
                unit_id=None,
                at=at,
                level="error",
                event_type="parser_broken",
                message=message,
            )
            return broken

        return await self._database.write(operation)

    async def reopen_parser_broken(self, run_id: str, *, at: datetime) -> CrawlRun:
        """Requeue only a manually retried parser-contract run.

        Successful units and their staged observations stay intact. Units cancelled by
        the fail-closed abort return to pending, so a fixed parser resumes from the exact
        durable checkpoint instead of rebuilding the whole day.
        """

        def operation(connection: sqlite3.Connection) -> CrawlRun:
            current = self._require_run(connection, run_id)
            reopened = current.reopen_after_parser_fix()
            failed_rows = connection.execute(
                "SELECT * FROM crawl_units WHERE run_id = ? AND status = ?",
                (run_id, RunUnitStatus.FAILED.value),
            ).fetchall()
            for row in failed_rows:
                unit = self._unit_from_row(row).requeue_after_parser_fix(at=at)
                self._update_unit(connection, unit)
            self._update_run(connection, reopened)
            self._append_event(
                connection,
                run_id=run_id,
                unit_id=None,
                at=at,
                level="info",
                event_type="run_reopened",
                message=(
                    "Ручное продолжение после исправления парсера: "
                    f"возвращено в очередь {len(failed_rows)} запросов"
                ),
            )
            return reopened

        return await self._database.write(operation)

    async def fail_run(
        self,
        run_id: str,
        *,
        code: str,
        message: str,
        at: datetime,
    ) -> CrawlRun:
        def operation(connection: sqlite3.Connection) -> CrawlRun:
            run = self._require_run(connection, run_id)
            failed = run.fail(code=code, message=message, at=at)
            self._cancel_incomplete_units(connection, run_id, message, at)
            self._update_run(connection, failed)
            self._append_event(
                connection,
                run_id=run_id,
                unit_id=None,
                at=at,
                level="error",
                event_type="run_failed",
                message=f"{code}: {message}",
            )
            return failed

        return await self._database.write(operation)

    async def expire_run(self, run_id: str, *, at: datetime) -> CrawlRun:
        def operation(connection: sqlite3.Connection) -> CrawlRun:
            run = self._require_run(connection, run_id)
            expired = run.expire(at=at)
            message = expired.error_message or "daily crawl expired"
            self._cancel_incomplete_units(connection, run_id, message, at)
            self._update_run(connection, expired)
            self._append_event(
                connection,
                run_id=run_id,
                unit_id=None,
                at=at,
                level="error",
                event_type="run_expired",
                message=message,
            )
            return expired

        return await self._database.write(operation)

    async def publish_completed(self, run_id: str, *, at: datetime) -> CrawlRun:
        def operation(connection: sqlite3.Connection) -> CrawlRun:
            run = self._require_run(connection, run_id)
            if run.status is RunStatus.SUCCEEDED:
                self._assert_published(connection, run)
                return run
            self._assert_ready_to_publish(connection, run)
            succeeded = run.succeed(at=at)
            connection.execute(
                """
                INSERT INTO search_observations (
                    run_id, unit_id, observation_json, published_at
                )
                SELECT run_id, unit_id, observation_json, ?
                FROM staged_search_observations
                WHERE run_id = ?
                ON CONFLICT(run_id, unit_id) DO UPDATE SET
                    observation_json = excluded.observation_json,
                    published_at = excluded.published_at
                """,
                (self._datetime_to_db(at), run_id),
            )
            connection.execute(
                "DELETE FROM staged_search_observations WHERE run_id = ?",
                (run_id,),
            )
            self._update_run(connection, succeeded)
            self._append_event(
                connection,
                run_id=run_id,
                unit_id=None,
                at=at,
                level="success",
                event_type="run_published",
                message=f"Опубликован полный срез: {run.total_units} наблюдений",
            )
            return succeeded

        return await self._database.write(operation)

    async def progress(self, run_id: str) -> CrawlProgress:
        def operation(connection: sqlite3.Connection) -> CrawlProgress:
            run = self._require_run(connection, run_id)
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS amount, COALESCE(SUM(attempts), 0) AS attempts
                FROM crawl_units WHERE run_id = ? GROUP BY status
                """,
                (run_id,),
            ).fetchall()
            counts = {str(row["status"]): int(row["amount"]) for row in rows}
            attempts = sum(int(row["attempts"]) for row in rows)
            retry_row = connection.execute(
                """
                SELECT MIN(retry_at) FROM crawl_units
                WHERE run_id = ? AND status = ?
                """,
                (run_id, RunUnitStatus.WAITING_RETRY.value),
            ).fetchone()
            retry_value = retry_row[0] if retry_row is not None else None
            return CrawlProgress(
                run_id=run.id,
                status=run.status,
                total_units=run.total_units,
                completed_units=run.completed_units,
                pending_units=counts.get(RunUnitStatus.PENDING.value, 0),
                running_units=counts.get(RunUnitStatus.RUNNING.value, 0),
                waiting_retry_units=counts.get(RunUnitStatus.WAITING_RETRY.value, 0),
                failed_units=counts.get(RunUnitStatus.FAILED.value, 0),
                total_attempts=attempts,
                next_retry_at=self._datetime_from_db(retry_value),
            )

        return await self._database.read(operation)

    async def list_units(self, run_id: str) -> Sequence[CrawlUnit]:
        def operation(connection: sqlite3.Connection) -> tuple[CrawlUnit, ...]:
            rows = connection.execute(
                "SELECT * FROM crawl_units WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            return tuple(self._unit_from_row(row) for row in rows)

        return await self._database.read(operation)

    async def list_events(self, run_id: str, *, limit: int = 200) -> Sequence[CrawlEvent]:
        bounded_limit = max(1, min(limit, 1000))

        def operation(connection: sqlite3.Connection) -> tuple[CrawlEvent, ...]:
            rows = connection.execute(
                """
                SELECT * FROM crawl_events
                WHERE run_id = ? ORDER BY id DESC LIMIT ?
                """,
                (run_id, bounded_limit),
            ).fetchall()
            return tuple(
                CrawlEvent(
                    id=int(row["id"]),
                    run_id=str(row["run_id"]),
                    unit_id=str(row["unit_id"]) if row["unit_id"] is not None else None,
                    occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
                    level=str(row["level"]),
                    event_type=str(row["event_type"]),
                    message=str(row["message"]),
                )
                for row in rows
            )

        return await self._database.read(operation)

    def _assert_ready_to_publish(self, connection: sqlite3.Connection, run: CrawlRun) -> None:
        if run.status not in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE}:
            raise InvalidStateTransition(f"cannot publish run from {run.status}")
        succeeded_units = int(
            connection.execute(
                "SELECT COUNT(*) FROM crawl_units WHERE run_id = ? AND status = ?",
                (run.id, RunUnitStatus.SUCCEEDED.value),
            ).fetchone()[0]
        )
        staged = int(
            connection.execute(
                "SELECT COUNT(*) FROM staged_search_observations WHERE run_id = ?",
                (run.id,),
            ).fetchone()[0]
        )
        expected = run.total_units
        if run.completed_units != expected or succeeded_units != expected or staged != expected:
            raise InvalidStateTransition(
                "cannot publish until run counters, succeeded units and staging all match"
            )

    @staticmethod
    def _assert_published(connection: sqlite3.Connection, run: CrawlRun) -> None:
        published = int(
            connection.execute(
                "SELECT COUNT(*) FROM search_observations WHERE run_id = ?",
                (run.id,),
            ).fetchone()[0]
        )
        if published != run.total_units:
            raise RuntimeError("succeeded run is missing published observations")

    def _cancel_incomplete_units(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        message: str,
        at: datetime,
    ) -> None:
        rows = connection.execute(
            """
            SELECT * FROM crawl_units
            WHERE run_id = ? AND status NOT IN (?, ?)
            """,
            (run_id, RunUnitStatus.SUCCEEDED.value, RunUnitStatus.FAILED.value),
        ).fetchall()
        for row in rows:
            self._update_unit(connection, self._unit_from_row(row).cancel(error=message, at=at))

    @classmethod
    def _append_event(
        cls,
        connection: sqlite3.Connection,
        *,
        run_id: str,
        unit_id: str | None,
        at: datetime | None,
        level: str,
        event_type: str,
        message: str,
    ) -> None:
        if at is None:
            raise ValueError("crawl event timestamp must not be empty")
        connection.execute(
            """
            INSERT INTO crawl_events (
                run_id, unit_id, occurred_at, level, event_type, message
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, unit_id, cls._datetime_to_db(at), level, event_type, message),
        )

    @staticmethod
    def _query_message(unit: CrawlUnit, *, prefix: str) -> str:
        query = unit.query
        return (
            f"{prefix}: роль {query.professional_role_id}, {query.experience.value}, "
            f"{query.target.value}, регион {query.region_id}"
        )

    @staticmethod
    def _unit_count(connection: sqlite3.Connection, run_id: str) -> int:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM crawl_units WHERE run_id = ?",
                (run_id,),
            ).fetchone()[0]
        )

    def _require_active_run(self, connection: sqlite3.Connection, run_id: str) -> CrawlRun:
        run = self._require_run(connection, run_id)
        if run.status not in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE}:
            raise InvalidStateTransition(f"run {run_id!r} is not active: {run.status}")
        return run

    def _require_run(self, connection: sqlite3.Connection, run_id: str) -> CrawlRun:
        row = connection.execute(
            "SELECT * FROM crawl_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"crawl run {run_id!r} does not exist")
        return self._run_from_row(row)

    def _require_unit(self, connection: sqlite3.Connection, unit_id: str) -> CrawlUnit:
        row = connection.execute(
            "SELECT * FROM crawl_units WHERE id = ?",
            (unit_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"crawl unit {unit_id!r} does not exist")
        return self._unit_from_row(row)

    @classmethod
    def _update_run(cls, connection: sqlite3.Connection, run: CrawlRun) -> None:
        cursor = connection.execute(
            """
            UPDATE crawl_runs SET
                job_id = ?, observation_date = ?, status = ?, total_units = ?,
                completed_units = ?, started_at = ?, finished_at = ?, error_code = ?,
                error_message = ?
            WHERE id = ?
            """,
            (*cls._run_to_row(run)[1:], run.id),
        )
        if cursor.rowcount != 1:
            raise KeyError(f"crawl run {run.id!r} does not exist")

    @classmethod
    def _update_unit(cls, connection: sqlite3.Connection, unit: CrawlUnit) -> None:
        cursor = connection.execute(
            """
            UPDATE crawl_units SET
                run_id = ?, query_json = ?, status = ?, attempts = ?, updated_at = ?,
                last_error = ?, retry_at = ?, worker_id = ?
            WHERE id = ?
            """,
            (*cls._unit_to_row(unit)[1:], unit.id),
        )
        if cursor.rowcount != 1:
            raise KeyError(f"crawl unit {unit.id!r} does not exist")

    @classmethod
    def _run_to_row(cls, run: CrawlRun) -> tuple[object, ...]:
        return (
            run.id,
            run.job_id,
            run.observation_date.isoformat(),
            run.status.value,
            run.total_units,
            run.completed_units,
            cls._datetime_to_db(run.started_at),
            cls._datetime_to_db(run.finished_at),
            run.error_code,
            run.error_message,
        )

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> CrawlRun:
        return CrawlRun(
            id=str(row["id"]),
            job_id=str(row["job_id"]),
            observation_date=date.fromisoformat(str(row["observation_date"])),
            status=RunStatus(str(row["status"])),
            total_units=int(row["total_units"]),
            completed_units=int(row["completed_units"]),
            started_at=SqliteCrawlExecutionRepository._datetime_from_db(row["started_at"]),
            finished_at=SqliteCrawlExecutionRepository._datetime_from_db(row["finished_at"]),
            error_code=str(row["error_code"]) if row["error_code"] is not None else None,
            error_message=(str(row["error_message"]) if row["error_message"] is not None else None),
        )

    @classmethod
    def _unit_to_row(cls, unit: CrawlUnit) -> tuple[object, ...]:
        return (
            unit.id,
            unit.run_id,
            query_to_json(unit.query),
            unit.status.value,
            unit.attempts,
            cls._datetime_to_db(unit.updated_at),
            unit.last_error,
            cls._datetime_to_db(unit.retry_at),
            unit.worker_id,
        )

    @staticmethod
    def _unit_from_row(row: sqlite3.Row) -> CrawlUnit:
        return CrawlUnit(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            query=query_from_json(str(row["query_json"])),
            status=RunUnitStatus(str(row["status"])),
            attempts=int(row["attempts"]),
            updated_at=SqliteCrawlExecutionRepository._datetime_from_db(row["updated_at"]),
            last_error=str(row["last_error"]) if row["last_error"] is not None else None,
            retry_at=SqliteCrawlExecutionRepository._datetime_from_db(row["retry_at"]),
            worker_id=str(row["worker_id"]) if row["worker_id"] is not None else None,
        )

    @staticmethod
    def _datetime_to_db(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("persisted datetime must be timezone-aware")
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _datetime_from_db(value: object) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(str(value))
