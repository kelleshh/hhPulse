from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    region_ids_json TEXT NOT NULL,
    role_selection_mode TEXT NOT NULL,
    role_ids_json TEXT NOT NULL,
    include_experience_strata INTEGER NOT NULL,
    max_concurrency INTEGER NOT NULL,
    max_rps REAL NOT NULL,
    user_agent_mode TEXT NOT NULL,
    timezone TEXT NOT NULL,
    methodology_version TEXT NOT NULL,
    active_resume_window_days INTEGER NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    observation_date TEXT NOT NULL,
    status TEXT NOT NULL,
    total_units INTEGER NOT NULL,
    completed_units INTEGER NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error_code TEXT,
    error_message TEXT,
    UNIQUE(job_id, observation_date)
);

CREATE INDEX IF NOT EXISTS idx_crawl_runs_job_date
    ON crawl_runs(job_id, observation_date);

CREATE TABLE IF NOT EXISTS crawl_units (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    query_json TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    updated_at TEXT,
    last_error TEXT,
    retry_at TEXT,
    worker_id TEXT,
    UNIQUE(run_id, query_json)
);

CREATE INDEX IF NOT EXISTS idx_crawl_units_run_status
    ON crawl_units(run_id, status);

CREATE TABLE IF NOT EXISTS staged_search_observations (
    run_id TEXT NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    unit_id TEXT NOT NULL REFERENCES crawl_units(id) ON DELETE CASCADE,
    observation_json TEXT NOT NULL,
    PRIMARY KEY(run_id, unit_id)
);

CREATE TABLE IF NOT EXISTS search_observations (
    run_id TEXT NOT NULL REFERENCES crawl_runs(id) ON DELETE CASCADE,
    unit_id TEXT NOT NULL,
    observation_json TEXT NOT NULL,
    published_at TEXT NOT NULL,
    PRIMARY KEY(run_id, unit_id)
);

CREATE INDEX IF NOT EXISTS idx_search_observations_run
    ON search_observations(run_id);
"""


class SqliteDatabase:
    """Tiny async boundary around sqlite3 for a local single-user control plane."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._write_lock = asyncio.Lock()

    async def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            self._migrate(connection)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(crawl_units)").fetchall()
        }
        if "retry_at" not in columns:
            connection.execute("ALTER TABLE crawl_units ADD COLUMN retry_at TEXT")
        if "worker_id" not in columns:
            connection.execute("ALTER TABLE crawl_units ADD COLUMN worker_id TEXT")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_crawl_units_ready
            ON crawl_units(run_id, status, retry_at)
            """
        )

    async def read(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self._run_sync, operation)

    async def write(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        async with self._write_lock:
            return await asyncio.to_thread(self._run_sync, operation)

    def _run_sync(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        with self._connect() as connection:
            try:
                result = operation(connection)
                connection.commit()
                return result
            except BaseException:
                connection.rollback()
                raise

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
