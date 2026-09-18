from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime

from hhpulse.application.ports.analytics import (
    AnalyticsReadRepository,
    PublishedObservation,
    RunRecord,
)
from hhpulse.domain.entities import CrawlRun
from hhpulse.domain.enums import RunStatus
from hhpulse.infrastructure.persistence.codec import observation_from_json
from hhpulse.infrastructure.persistence.database import SqliteDatabase


class SqliteAnalyticsReadRepository(AnalyticsReadRepository):
    def __init__(self, database: SqliteDatabase) -> None:
        self._database = database

    async def list_observations(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> tuple[PublishedObservation, ...]:
        def operation(connection: sqlite3.Connection) -> tuple[PublishedObservation, ...]:
            rows = connection.execute(
                """
                SELECT so.observation_json, so.published_at
                FROM search_observations AS so
                JOIN crawl_runs AS cr ON cr.id = so.run_id
                WHERE cr.observation_date BETWEEN ? AND ?
                ORDER BY so.published_at, so.run_id, so.unit_id
                """,
                (date_from.isoformat(), date_to.isoformat()),
            ).fetchall()
            return tuple(
                PublishedObservation(
                    observation=observation_from_json(str(row["observation_json"])),
                    published_at=datetime.fromisoformat(str(row["published_at"])),
                )
                for row in rows
            )

        return await self._database.read(operation)

    async def list_runs(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> tuple[RunRecord, ...]:
        def operation(connection: sqlite3.Connection) -> tuple[RunRecord, ...]:
            rows = connection.execute(
                """
                SELECT cr.*, aj.name AS job_name
                FROM crawl_runs AS cr
                JOIN analysis_jobs AS aj ON aj.id = cr.job_id
                WHERE cr.observation_date BETWEEN ? AND ?
                ORDER BY cr.observation_date, cr.started_at, cr.id
                """,
                (date_from.isoformat(), date_to.isoformat()),
            ).fetchall()
            return tuple(
                RunRecord(run=self._run_from_row(row), job_name=str(row["job_name"]))
                for row in rows
            )

        return await self._database.read(operation)

    async def resolve_alert(self, alert_id: str, *, at: datetime) -> None:
        def operation(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO resolved_alerts (alert_id, resolved_at) VALUES (?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET resolved_at = excluded.resolved_at
                """,
                (alert_id, at.astimezone(UTC).isoformat()),
            )

        await self._database.write(operation)

    async def list_resolved_alert_ids(self) -> set[str]:
        def operation(connection: sqlite3.Connection) -> set[str]:
            rows = connection.execute("SELECT alert_id FROM resolved_alerts").fetchall()
            return {str(row["alert_id"]) for row in rows}

        return await self._database.read(operation)

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> CrawlRun:
        return CrawlRun(
            id=str(row["id"]),
            job_id=str(row["job_id"]),
            observation_date=date.fromisoformat(str(row["observation_date"])),
            status=RunStatus(str(row["status"])),
            total_units=int(row["total_units"]),
            completed_units=int(row["completed_units"]),
            started_at=(
                datetime.fromisoformat(str(row["started_at"]))
                if row["started_at"] is not None
                else None
            ),
            finished_at=(
                datetime.fromisoformat(str(row["finished_at"]))
                if row["finished_at"] is not None
                else None
            ),
            error_code=str(row["error_code"]) if row["error_code"] is not None else None,
            error_message=(str(row["error_message"]) if row["error_message"] is not None else None),
        )
