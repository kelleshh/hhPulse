class DomainError(ValueError):
    """Base error for violated domain invariants."""


class InvalidStateTransition(DomainError):
    """Raised when an aggregate transition is not allowed."""
