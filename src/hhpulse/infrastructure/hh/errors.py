from hhpulse.application.errors import (
    MarketSourceError,
    MarketSourceRejected,
    MarketSourceThrottled,
    MarketSourceUnavailable,
    ParserContractBroken,
)

HhInfrastructureError = MarketSourceError
HhSourceUnavailable = MarketSourceUnavailable
HhThrottled = MarketSourceThrottled
HhAccessRejected = MarketSourceRejected
HhParserContractBroken = ParserContractBroken

__all__ = [
    "HhAccessRejected",
    "HhInfrastructureError",
    "HhParserContractBroken",
    "HhSourceUnavailable",
    "HhThrottled",
]
