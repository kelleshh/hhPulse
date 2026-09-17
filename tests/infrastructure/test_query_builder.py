from datetime import date

from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.value_objects import SearchQuery
from hhpulse.infrastructure.hh.query_builder import HhQueryBuilder


def test_resume_query_uses_exact_60_day_active_window_and_relocation_contract() -> None:
    query = SearchQuery(
        target=SearchTarget.RESUME,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
        experience=ExperienceBand.BETWEEN_1_AND_3,
    )

    params = HhQueryBuilder().build(query)

    assert ("date_from", "20.07.2026") in params
    assert ("date_to", "17.09.2026") in params
    assert ("relocation", "living_or_relocation") in params
    assert params.count(("job_search_status", "active_search")) == 1
    assert params.count(("job_search_status", "looking_for_offers")) == 1
    assert params.count(("job_search_status", "unknown")) == 1
    assert ("experience", "between1And3") in params


def test_vacancy_query_does_not_add_experience_for_any_band() -> None:
    query = SearchQuery(
        target=SearchTarget.VACANCY,
        observation_date=date(2026, 9, 17),
        region_id="1",
        professional_role_id="96",
    )

    params = HhQueryBuilder().build(query)

    assert not any(key == "experience" for key, _ in params)
    assert ("professional_role", "96") in params
