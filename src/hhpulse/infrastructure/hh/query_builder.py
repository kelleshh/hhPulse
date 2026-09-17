from __future__ import annotations

from datetime import timedelta

from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.value_objects import Methodology, SearchQuery

HttpParams = tuple[tuple[str, str], ...]


class HhQueryBuilder:
    def __init__(self, methodology: Methodology | None = None) -> None:
        self._methodology = methodology or Methodology()

    def build(self, query: SearchQuery) -> HttpParams:
        if query.target is SearchTarget.VACANCY:
            params = self._vacancy_params(query)
        else:
            params = self._resume_params(query)
        return tuple(params)

    def vacancy_catalog_params(self, *, region_id: str) -> HttpParams:
        return (
            ("area", region_id),
            ("ored_clusters", "true"),
            ("items_on_page", "20"),
        )

    def _vacancy_params(self, query: SearchQuery) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = [
            ("area", query.region_id),
            ("professional_role", query.professional_role_id),
            ("ored_clusters", "true"),
            ("items_on_page", "20"),
        ]
        if query.experience is not ExperienceBand.ANY:
            params.append(("experience", query.experience.value))
        self._append_extra_filters(params, query)
        return params

    def _resume_params(self, query: SearchQuery) -> list[tuple[str, str]]:
        date_to = query.observation_date
        date_from = date_to - timedelta(days=self._methodology.active_resume_window_days - 1)
        params: list[tuple[str, str]] = [
            ("logic", "normal"),
            ("pos", "full_text"),
            ("exp_period", "all_time"),
            ("filter_exp_period", "all_time"),
            ("area", query.region_id),
            ("relocation", "living_or_relocation"),
            ("job_search_status", "active_search"),
            ("job_search_status", "looking_for_offers"),
            ("job_search_status", "unknown"),
            ("order_by", "relevance"),
            ("search_period", "-1"),
            ("date_from", date_from.strftime("%d.%m.%Y")),
            ("date_to", date_to.strftime("%d.%m.%Y")),
            ("items_on_page", "50"),
            ("no_magic", "true"),
            ("ored_clusters", "true"),
            ("professional_role", query.professional_role_id),
        ]
        if query.experience is not ExperienceBand.ANY:
            params.append(("experience", query.experience.value))
        self._append_extra_filters(params, query)
        return params

    @staticmethod
    def _append_extra_filters(params: list[tuple[str, str]], query: SearchQuery) -> None:
        for query_filter in query.extra_filters:
            params.extend((query_filter.key, value) for value in query_filter.values)
