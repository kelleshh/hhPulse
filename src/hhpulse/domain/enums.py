from enum import StrEnum


class SearchTarget(StrEnum):
    VACANCY = "vacancy"
    RESUME = "resume"


class ExperienceBand(StrEnum):
    ANY = "any"
    NO_EXPERIENCE = "noExperience"
    BETWEEN_1_AND_3 = "between1And3"
    BETWEEN_3_AND_6 = "between3And6"
    MORE_THAN_6 = "moreThan6"


class RoleSelectionMode(StrEnum):
    ALL = "all"
    SELECTED = "selected"


class UserAgentMode(StrEnum):
    SHARED = "shared"
    PER_WORKER = "per_worker"


class RunStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    WAITING_SOURCE = "waiting_source"
    PARSER_BROKEN = "parser_broken"
    FAILED = "failed"
    EXPIRED = "expired"
    SUCCEEDED = "succeeded"


class RunUnitStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_RETRY = "waiting_retry"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
