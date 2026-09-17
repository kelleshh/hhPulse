from __future__ import annotations


class MarketSourceError(RuntimeError):
    """Base error exposed by market-source adapters to application services."""


class MarketSourceUnavailable(MarketSourceError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class MarketSourceThrottled(MarketSourceUnavailable):
    """The source explicitly asked the crawler to slow down."""


class ParserContractBroken(MarketSourceError):
    def __init__(self, message: str, *, raw_html: str | None = None) -> None:
        super().__init__(message)
        self.raw_html = raw_html
