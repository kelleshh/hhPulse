from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Sequence

from hhpulse.application.ports.repositories import (
    AnalysisJobRepository,
    CrawlRunRepository,
    CrawlUnitRepository,
    ObservationRepository,
)
from hhpulse.domain.entities import AnalysisJob, AnalysisScope, CrawlRun, CrawlUnit
from hhpulse.domain.enums import RoleSelectionMode, RunStatus, RunUnitStatus, UserAgentMode
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
                "SELECT * FROM analysis_jobs WHERE id = ?", (job_id,)
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
                self._to_update_row(job),
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

    @classmethod
    def _to_update_row(cls, job: AnalysisJob) -> tuple[object, ...]:
        row = cls._to_row(job)
        return (*row[1:], job.id)

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


class SqliteCrawlRunRepository(CrawlRunRepository):
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    async def add(self, run: CrawlRun) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO crawl_runs (
                    id, job_id, observation_date, status, total_units, completed_units,
                    started_at, finished_at, error_code, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._to_row(run),
            )

        await self._database.write(operation)

    async def get(self, run_id: str) -> CrawlRun | None:
        def operation(connection: sqlite3.Connection) -> CrawlRun | None:
            row = connection.execute("SELECT * FROM crawl_runs WHERE id = ?", (run_id,)).fetchone()
            return self._from_row(row) if row is not None else None

        return await self._database.read(operation)

    async def get_for_job_date(self, job_id: str, observation_date: date) -> CrawlRun | None:
        def operation(connection: sqlite3.Connection) -> CrawlRun | None:
            row = connection.execute(
                "SELECT * FROM crawl_runs WHERE job_id = ? AND observation_date = ?",
                (job_id, observation_date.isoformat()),
            ).fetchone()
            return self._from_row(row) if row is not None else None

        return await self._database.read(operation)

    async def update(self, run: CrawlRun) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            cursor = connection.execute(
                """
                UPDATE crawl_runs SET
                    job_id = ?, observation_date = ?, status = ?, total_units = ?,
                    completed_units = ?, started_at = ?, finished_at = ?, error_code = ?,
                    error_message = ?
                WHERE id = ?
                """,
                (*self._to_row(run)[1:], run.id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"crawl run {run.id!r} does not exist")

        await self._database.write(operation)

    @staticmethod
    def _to_row(run: CrawlRun) -> tuple[object, ...]:
        return (
            run.id,
            run.job_id,
            run.observation_date.isoformat(),
            run.status.value,
            run.total_units,
            run.completed_units,
            run.started_at.isoformat() if run.started_at else None,
            run.finished_at.isoformat() if run.finished_at else None,
            run.error_code,
            run.error_message,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CrawlRun:
        started_at = str(row["started_at"]) if row["started_at"] is not None else None
        finished_at = str(row["finished_at"]) if row["finished_at"] is not None else None
        return CrawlRun(
            id=str(row["id"]),
            job_id=str(row["job_id"]),
            observation_date=date.fromisoformat(str(row["observation_date"])),
            status=RunStatus(str(row["status"])),
            total_units=int(row["total_units"]),
            completed_units=int(row["completed_units"]),
            started_at=datetime.fromisoformat(started_at) if started_at else None,
            finished_at=datetime.fromisoformat(finished_at) if finished_at else None,
            error_code=str(row["error_code"]) if row["error_code"] is not None else None,
            error_message=str(row["error_message"]) if row["error_message"] is not None else None,
        )


class SqliteCrawlUnitRepository(CrawlUnitRepository):
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    async def add_many(self, units: Sequence[CrawlUnit]) -> None:
        if not units:
            return

        def operation(connection: sqlite3.Connection) -> None:
            connection.executemany(
                """
                INSERT INTO crawl_units (
                    id, run_id, query_json, status, attempts, updated_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [self._to_row(unit) for unit in units],
            )

        await self._database.write(operation)

    async def list_for_run(self, run_id: str) -> Sequence[CrawlUnit]:
        def operation(connection: sqlite3.Connection) -> tuple[CrawlUnit, ...]:
            rows = connection.execute(
                "SELECT * FROM crawl_units WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)

        return await self._database.read(operation)

    async def list_incomplete_for_run(self, run_id: str) -> Sequence[CrawlUnit]:
        terminal = (RunUnitStatus.SUCCEEDED.value, RunUnitStatus.FAILED.value)

        def operation(connection: sqlite3.Connection) -> tuple[CrawlUnit, ...]:
            rows = connection.execute(
                """
                SELECT * FROM crawl_units
                WHERE run_id = ? AND status NOT IN (?, ?)
                ORDER BY id
                """,
                (run_id, *terminal),
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)

        return await self._database.read(operation)

    async def update(self, unit: CrawlUnit) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            cursor = connection.execute(
                """
                UPDATE crawl_units SET
                    run_id = ?, query_json = ?, status = ?, attempts = ?,
                    updated_at = ?, last_error = ?
                WHERE id = ?
                """,
                (*self._to_row(unit)[1:], unit.id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"crawl unit {unit.id!r} does not exist")

        await self._database.write(operation)

    @staticmethod
    def _to_row(unit: CrawlUnit) -> tuple[object, ...]:
        return (
            unit.id,
            unit.run_id,
            query_to_json(unit.query),
            unit.status.value,
            unit.attempts,
            unit.updated_at.isoformat() if unit.updated_at else None,
            unit.last_error,
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> CrawlUnit:
        updated_at = str(row["updated_at"]) if row["updated_at"] is not None else None
        return CrawlUnit(
            id=str(row["id"]),
            run_id=str(row["run_id"]),
            query=query_from_json(str(row["query_json"])),
            status=RunUnitStatus(str(row["status"])),
            attempts=int(row["attempts"]),
            updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
            last_error=str(row["last_error"]) if row["last_error"] is not None else None,
        )


class SqliteObservationRepository(ObservationRepository):
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    async def stage(self, run_id: str, unit_id: str, observation: SearchObservation) -> None:
        payload = observation_to_json(observation)

        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO staged_search_observations (run_id, unit_id, observation_json)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id, unit_id) DO UPDATE SET
                    observation_json = excluded.observation_json
                """,
                (run_id, unit_id, payload),
            )

        await self._database.write(operation)

    async def publish_run(self, run_id: str) -> None:
        """Atomically promotes every staged observation for a completed run."""

        def operation(connection: sqlite3.Connection) -> None:
            run = connection.execute(
                "SELECT status, total_units, completed_units FROM crawl_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(f"crawl run {run_id!r} does not exist")
            if str(run["status"]) != RunStatus.SUCCEEDED.value:
                raise ValueError("only a succeeded run can be published")
            if int(run["completed_units"]) != int(run["total_units"]):
                raise ValueError("cannot publish an incomplete run")

            staged_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM staged_search_observations WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            if staged_count != int(run["total_units"]):
                raise ValueError(
                    f"staged observation count {staged_count} does not match run total "
                    f"{int(run['total_units'])}"
                )

            published_at = datetime.now().astimezone().isoformat()
            connection.execute(
                """
                INSERT INTO search_observations (run_id, unit_id, observation_json, published_at)
                SELECT run_id, unit_id, observation_json, ?
                FROM staged_search_observations
                WHERE run_id = ?
                ON CONFLICT(run_id, unit_id) DO UPDATE SET
                    observation_json = excluded.observation_json,
                    published_at = excluded.published_at
                """,
                (published_at, run_id),
            )
            connection.execute(
                "DELETE FROM staged_search_observations WHERE run_id = ?", (run_id,)
            )

        await self._database.write(operation)

    async def discard_staging(self, run_id: str) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                "DELETE FROM staged_search_observations WHERE run_id = ?", (run_id,)
            )

        await self._database.write(operation)
