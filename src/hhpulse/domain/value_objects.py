from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class ProfessionalRole:
    id: str
    name: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainError("professional role id must not be empty")
        if not self.name.strip():
            raise DomainError("professional role name must not be empty")


@dataclass(frozen=True, slots=True)
class Region:
    id: str
    name: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainError("region id must not be empty")
        if not self.name.strip():
            raise DomainError("region name must not be empty")


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    max_concurrency: int = 1
    max_rps: float = 1.0

    def __post_init__(self) -> None:
        if self.max_concurrency < 1:
            raise DomainError("max_concurrency must be >= 1")
        if self.max_rps <= 0:
            raise DomainError("max_rps must be > 0")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    initial_delay_seconds: float = 5.0
    max_delay_seconds: float = 900.0

    def __post_init__(self) -> None:
        if self.initial_delay_seconds <= 0:
            raise DomainError("initial retry delay must be positive")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise DomainError("max retry delay must not be smaller than initial delay")

    def delay_seconds(
        self,
        *,
        attempts: int,
        retry_after_seconds: float | None = None,
    ) -> float:
        if attempts < 1:
            raise DomainError("retry delay requires at least one attempt")
        exponential = self.initial_delay_seconds * float(2 ** min(attempts - 1, 16))
        requested = retry_after_seconds or 0.0
        return min(self.max_delay_seconds, max(exponential, requested))


@dataclass(frozen=True, slots=True)
class DailySchedule:
    timezone: str = "Europe/Moscow"

    def __post_init__(self) -> None:
        if not self.timezone.strip():
            raise DomainError("timezone must not be empty")


@dataclass(frozen=True, slots=True)
class Methodology:
    version: str = "hh-index-daily-v1"
    active_resume_window_days: int = 60

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise DomainError("methodology version must not be empty")
        if self.active_resume_window_days < 1:
            raise DomainError("active resume window must be positive")


@dataclass(frozen=True, slots=True)
class QueryFilter:
    key: str
    values: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise DomainError("filter key must not be empty")
        if not self.values:
            raise DomainError("filter values must not be empty")
        if any(not value.strip() for value in self.values):
            raise DomainError("filter values must not contain empty strings")

    @classmethod
    def one(cls, key: str, value: str) -> QueryFilter:
        return cls(key=key, values=(value,))


@dataclass(frozen=True, slots=True)
class SearchQuery:
    target: SearchTarget
    observation_date: date
    region_id: str
    professional_role_id: str
    experience: ExperienceBand = ExperienceBand.ANY
    extra_filters: tuple[QueryFilter, ...] = ()

    def __post_init__(self) -> None:
        if not self.region_id.strip():
            raise DomainError("region id must not be empty")
        if not self.professional_role_id.strip():
            raise DomainError("professional role id must not be empty")
        keys = [flt.key for flt in self.extra_filters]
        if len(keys) != len(set(keys)):
            raise DomainError("extra filter keys must be unique")


@dataclass(frozen=True, slots=True)
class FacetOptionCount:
    id: str
    title: str
    count: int
    query: str | None = None
    disabled: bool = False

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise DomainError("facet option id must not be empty")
        if not self.title.strip():
            raise DomainError("facet option title must not be empty")
        if self.count < 0:
            raise DomainError("facet count must not be negative")


@dataclass(frozen=True, slots=True)
class FacetGroup:
    key: str
    options: tuple[FacetOptionCount, ...]

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise DomainError("facet key must not be empty")
        option_ids = [option.id for option in self.options]
        if len(option_ids) != len(set(option_ids)):
            raise DomainError(f"facet {self.key!r} contains duplicate option ids")

    def get(self, option_id: str) -> FacetOptionCount | None:
        return next((option for option in self.options if option.id == option_id), None)


@dataclass(frozen=True, slots=True)
class ParsedSearchPage:
    total_count: int
    facets: tuple[FacetGroup, ...]

    def __post_init__(self) -> None:
        if self.total_count < 0:
            raise DomainError("search total must not be negative")
        keys = [facet.key for facet in self.facets]
        if len(keys) != len(set(keys)):
            raise DomainError("facet keys must be unique")

    def facet(self, key: str) -> FacetGroup | None:
        return next((facet for facet in self.facets if facet.key == key), None)

    def roles(self) -> tuple[ProfessionalRole, ...]:
        role_facet = self.facet("professional_role")
        if role_facet is None:
            return ()
        return tuple(
            ProfessionalRole(id=option.id, name=option.title) for option in role_facet.options
        )


@dataclass(frozen=True, slots=True)
class SearchObservation:
    query: SearchQuery
    page: ParsedSearchPage


@dataclass(frozen=True, slots=True)
class HhIndex:
    resume_count: int
    vacancy_count: int

    def __post_init__(self) -> None:
        if self.resume_count < 0 or self.vacancy_count < 0:
            raise DomainError("hh-index counts must not be negative")

    @property
    def value(self) -> float | None:
        if self.vacancy_count == 0:
            return None
        return self.resume_count / self.vacancy_count


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    observation_date: date
    region_id: str
    professional_role_id: str
    experience: ExperienceBand
    vacancy: ParsedSearchPage
    resume: ParsedSearchPage
    methodology_version: str

    @property
    def hh_index(self) -> HhIndex:
        return HhIndex(
            resume_count=self.resume.total_count,
            vacancy_count=self.vacancy.total_count,
        )


def unique_strings(values: Iterable[str], *, field_name: str) -> tuple[str, ...]:
    cleaned = tuple(value.strip() for value in values if value.strip())
    if len(cleaned) != len(set(cleaned)):
        raise DomainError(f"{field_name} must not contain duplicates")
    return cleaned
