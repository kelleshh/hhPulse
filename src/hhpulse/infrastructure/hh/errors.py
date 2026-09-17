from hhpulse.application.errors import (
    MarketSourceError,
    MarketSourceThrottled,
    MarketSourceUnavailable,
    ParserContractBroken,
)

HhInfrastructureError = MarketSourceError
HhSourceUnavailable = MarketSourceUnavailable
HhThrottled = MarketSourceThrottled
HhParserContractBroken = ParserContractBroken


__all__ = [
    "HhInfrastructureError",
    "HhParserContractBroken",
    "HhSourceUnavailable",
    "HhThrottled",
]
