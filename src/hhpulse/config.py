from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: str = "/data/hhpulse.sqlite3"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    quarantine_dir: str = "/data/quarantine"
    quarantine_retention_hours: float = 24.0
    source_timeout_seconds: float = 30.0
    retry_initial_seconds: float = 5.0
    retry_max_seconds: float = 900.0
    preflight_successes: int = 1
    scheduler_poll_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> Settings:
        defaults = cls()
        return cls(
            db_path=os.getenv("HHPULSE_DB_PATH", defaults.db_path),
            host=os.getenv("HHPULSE_HOST", defaults.host),
            port=int(os.getenv("HHPULSE_PORT", str(defaults.port))),
            log_level=os.getenv("HHPULSE_LOG_LEVEL", defaults.log_level),
            quarantine_dir=os.getenv("HHPULSE_QUARANTINE_DIR", defaults.quarantine_dir),
            quarantine_retention_hours=float(
                os.getenv(
                    "HHPULSE_QUARANTINE_RETENTION_HOURS",
                    str(defaults.quarantine_retention_hours),
                )
            ),
            source_timeout_seconds=float(
                os.getenv("HHPULSE_SOURCE_TIMEOUT_SECONDS", str(defaults.source_timeout_seconds))
            ),
            retry_initial_seconds=float(
                os.getenv("HHPULSE_RETRY_INITIAL_SECONDS", str(defaults.retry_initial_seconds))
            ),
            retry_max_seconds=float(
                os.getenv("HHPULSE_RETRY_MAX_SECONDS", str(defaults.retry_max_seconds))
            ),
            preflight_successes=int(
                os.getenv("HHPULSE_PREFLIGHT_SUCCESSES", str(defaults.preflight_successes))
            ),
            scheduler_poll_seconds=float(
                os.getenv("HHPULSE_SCHEDULER_POLL_SECONDS", str(defaults.scheduler_poll_seconds))
            ),
        )
