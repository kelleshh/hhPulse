class HhInfrastructureError(RuntimeError):
    """Base error for HH transport/parser failures."""


class HhSourceUnavailable(HhInfrastructureError):
    """HH is temporarily unavailable and the current run should wait."""


class HhThrottled(HhSourceUnavailable):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class HhParserContractBroken(HhInfrastructureError):
    """Returned HTML no longer satisfies the parser contract."""
