from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: str = "/data/hhpulse.sqlite3"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        defaults = cls()
        return cls(
            db_path=os.getenv("HHPULSE_DB_PATH", defaults.db_path),
            host=os.getenv("HHPULSE_HOST", defaults.host),
            port=int(os.getenv("HHPULSE_PORT", str(defaults.port))),
            log_level=os.getenv("HHPULSE_LOG_LEVEL", defaults.log_level),
        )
