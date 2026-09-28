from __future__ import annotations


class MarketSourceError(RuntimeError):
    """Base error exposed by market-source adapters to application services."""


class MarketSourceUnavailable(MarketSourceError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class MarketSourceThrottled(MarketSourceUnavailable):
    """The source explicitly asked the crawler to slow down."""


class BrowserUnavailable(MarketSourceUnavailable):
    """The local Chrome companion is disconnected; recheck it soon."""


class MarketSourceRejected(MarketSourceError):
    """The source rejected credentials or application access permanently."""


class ParserContractBroken(MarketSourceError):
    def __init__(self, message: str, *, raw_payload: str | None = None) -> None:
        super().__init__(message)
        self.raw_payload = raw_payload
