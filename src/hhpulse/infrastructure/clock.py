from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


class SystemClock:
    def __init__(self, timezone: str = "Europe/Moscow") -> None:
        self._timezone = ZoneInfo(timezone)

    def now(self) -> datetime:
        return datetime.now(self._timezone)

    def today(self) -> date:
        return self.now().date()
