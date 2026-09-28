from __future__ import annotations

from datetime import datetime

from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.value_objects import SearchQuery

HttpParams = tuple[tuple[str, str], ...]


class HhApiQueryBuilder:
    """Builds only documented api.hh.ru vacancy-search parameters."""

    def build_aggregate(self, query: SearchQuery) -> HttpParams:
        self._require_vacancy(query)
        params = self._base_params(query)
        params.extend((
            ("clusters", "true"),
            ("per_page", "1"),
        ))
        return tuple(params)

    def build_count(self, query: SearchQuery, *, key: str, value: str) -> HttpParams:
        self._require_vacancy(query)
        params = self._base_params(query, excluded_filter_key=key)
        params.extend(((key, value), ("per_page", "1")))
        return tuple(params)

    def build_response_page(
        self,
        query: SearchQuery,
        *,
        page: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> HttpParams:
        self._require_vacancy(query)
        if page < 0:
            raise ValueError("page must not be negative")
        params = self._base_params(query)
        params.extend(
            (
                ("responses_count_enabled", "true"),
                ("per_page", "100"),
                ("page", str(page)),
                ("order_by", "publication_time"),
            )
        )
        if date_from is not None:
            params.append(("date_from", date_from.isoformat()))
        if date_to is not None:
            params.append(("date_to", date_to.isoformat()))
        return tuple(params)

    def vacancy_catalog_params(self, *, region_id: str) -> HttpParams:
        return (
            ("area", region_id),
            ("clusters", "true"),
            ("per_page", "1"),
            ("no_magic", "true"),
        )

    @staticmethod
    def _require_vacancy(query: SearchQuery) -> None:
        if query.target is not SearchTarget.VACANCY:
            raise ValueError("official public HH adapter supports vacancy search only")

    @staticmethod
    def _base_params(
        query: SearchQuery,
        *,
        excluded_filter_key: str | None = None,
    ) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = [
            ("area", query.region_id),
            ("professional_role", query.professional_role_id),
            ("no_magic", "true"),
        ]
        if query.experience is not ExperienceBand.ANY and excluded_filter_key != "experience":
            params.append(("experience", query.experience.value))
        for query_filter in query.extra_filters:
            if query_filter.key == excluded_filter_key:
                continue
            params.extend((query_filter.key, value) for value in query_filter.values)
        return params
