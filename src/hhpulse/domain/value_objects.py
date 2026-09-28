from __future__ import annotations

from collections import Counter
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
    max_concurrency: int = 2
    max_rps: float = 2.0

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
    version: str = "hh-browser-per-role-v2"
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
class ResponseCountFrequency:
    responses: int
    vacancies: int

    def __post_init__(self) -> None:
        if self.responses < 0:
            raise DomainError("response count must not be negative")
        if self.vacancies < 1:
            raise DomainError("response histogram frequency must be positive")


@dataclass(frozen=True, slots=True)
class VacancyResponseStats:
    expected_vacancies: int
    observed_vacancies: int
    histogram: tuple[ResponseCountFrequency, ...]

    def __post_init__(self) -> None:
        if self.expected_vacancies < 0 or self.observed_vacancies < 0:
            raise DomainError("vacancy response-stat counts must not be negative")
        if sum(item.vacancies for item in self.histogram) != self.observed_vacancies:
            raise DomainError("response histogram must cover observed vacancies exactly")
        response_values = [item.responses for item in self.histogram]
        if response_values != sorted(response_values) or len(response_values) != len(
            set(response_values)
        ):
            raise DomainError("response histogram must be sorted and contain unique counts")

    @classmethod
    def from_counts(
        cls,
        counts: Iterable[int],
        *,
        expected_vacancies: int,
    ) -> VacancyResponseStats:
        materialized = tuple(counts)
        frequencies = Counter(materialized)
        return cls(
            expected_vacancies=expected_vacancies,
            observed_vacancies=len(materialized),
            histogram=tuple(
                ResponseCountFrequency(responses=value, vacancies=frequencies[value])
                for value in sorted(frequencies)
            ),
        )

    @property
    def complete(self) -> bool:
        return self.expected_vacancies == self.observed_vacancies

    @property
    def total_responses(self) -> int:
        return sum(item.responses * item.vacancies for item in self.histogram)

    @property
    def mean(self) -> float | None:
        if not self.observed_vacancies:
            return None
        return self.total_responses / self.observed_vacancies

    @property
    def median(self) -> float | None:
        return self.quantile(0.5)

    def quantile(self, fraction: float) -> float | None:
        if not 0.0 <= fraction <= 1.0:
            raise DomainError("quantile fraction must be between zero and one")
        if not self.observed_vacancies:
            return None
        position = (self.observed_vacancies - 1) * fraction
        lower = int(position)
        upper = lower if position == lower else lower + 1
        lower_value = self._value_at(lower)
        upper_value = self._value_at(upper)
        if lower == upper:
            return float(lower_value)
        return lower_value + (upper_value - lower_value) * (position - lower)

    def _value_at(self, position: int) -> int:
        seen = 0
        for item in self.histogram:
            seen += item.vacancies
            if position < seen:
                return item.responses
        raise DomainError("response histogram position is outside its range")


@dataclass(frozen=True, slots=True)
class ParsedSearchPage:
    total_count: int
    facets: tuple[FacetGroup, ...]
    response_stats: VacancyResponseStats | None = None
    methodology_version: str | None = None

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
