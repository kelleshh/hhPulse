from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.value_objects import SearchQuery
from hhpulse.infrastructure.hh.query_builder import HhApiQueryBuilder


def test_vacancy_aggregate_query_uses_official_cluster_mode() -> None:
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
        experience=ExperienceBand.BETWEEN_1_AND_3,
    )

    params = HhApiQueryBuilder().build_aggregate(query)

    assert ("area", "1") in params
    assert ("professional_role", "96") in params
    assert ("experience", "between1And3") in params
    assert ("clusters", "true") in params
    assert ("per_page", "1") in params
    assert ("no_magic", "true") in params
    assert not any(key in {"ored_clusters", "items_on_page", "hhtmFrom"} for key, _ in params)


def test_vacancy_any_band_does_not_add_experience() -> None:
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    params = HhApiQueryBuilder().build_aggregate(query)

    assert not any(key == "experience" for key, _ in params)


def test_response_page_uses_max_page_size_and_response_counter() -> None:
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )
    tz = ZoneInfo("Europe/Moscow")

    params = HhApiQueryBuilder().build_response_page(
        query,
        page=3,
        date_from=datetime(2026, 9, 1, tzinfo=tz),
        date_to=datetime(2026, 9, 2, 23, 59, 59, tzinfo=tz),
    )

    assert ("responses_count_enabled", "true") in params
    assert ("per_page", "100") in params
    assert ("page", "3") in params
    assert any(key == "date_from" for key, _ in params)
    assert any(key == "date_to" for key, _ in params)


def test_resume_query_is_not_implemented_by_public_vacancy_adapter() -> None:
    query = SearchQuery(
        target=SearchTarget.RESUME,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    with pytest.raises(ValueError, match="vacancy search only"):
        HhApiQueryBuilder().build_aggregate(query)
