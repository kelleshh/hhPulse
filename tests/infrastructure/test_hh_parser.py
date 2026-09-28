import json

import pytest

from hhpulse.infrastructure.hh.errors import HhParserContractBroken
from hhpulse.infrastructure.hh.parser import HhVacancySearchResponseParser


def _fixture_payload() -> str:
    return json.dumps(
        {
            "found": 1234,
            "items": [],
            "clusters": [
                {
                    "id": "experience",
                    "name": "Опыт работы",
                    "items": [
                        {
                            "name": "Нет опыта",
                            "url": "https://api.hh.ru/vacancies?experience=noExperience&area=1",
                            "count": 5,
                        },
                        {
                            "name": "От 1 года до 3 лет",
                            "url": "https://api.hh.ru/vacancies?experience=between1And3&area=1",
                            "count": 39,
                        },
                    ],
                },
                {
                    "id": "education",
                    "name": "Образование",
                    "items": [
                        {
                            "name": "Высшее",
                            "url": "https://api.hh.ru/vacancies?education=higher&area=1",
                            "count": 39,
                        }
                    ],
                },
                {
                    "id": "work_format",
                    "name": "Формат работы",
                    "items": [
                        {
                            "name": "Удалённо",
                            "url": "https://api.hh.ru/vacancies?work_format=REMOTE&area=1",
                            "count": 28,
                        },
                        {
                            "name": "Гибрид",
                            "url": "https://api.hh.ru/vacancies?work_format=HYBRID&area=1",
                            "count": 39,
                        },
                    ],
                },
                {
                    "id": "label",
                    "name": "Метки",
                    "items": [
                        {
                            "name": "Указан доход",
                            "url": "https://api.hh.ru/vacancies?label=with_salary&area=1",
                            "count": 8,
                        },
                        {
                            "name": "Меньше 10 откликов",
                            "url": "https://api.hh.ru/vacancies?label=low_performance&area=1",
                            "count": 35,
                        },
                    ],
                },
                {
                    "id": "professional_role",
                    "name": "Профессиональная роль",
                    "items": [
                        {
                            "name": "Программист, разработчик",
                            "url": "https://api.hh.ru/vacancies?professional_role=96&area=1",
                            "count": 100,
                        }
                    ],
                },
            ],
        },
        ensure_ascii=False,
    )


def test_parser_extracts_total_and_documented_clusters() -> None:
    page = HhVacancySearchResponseParser().parse(_fixture_payload())

    assert page.total_count == 1234
    assert page.facet("work_format").get("REMOTE").count == 28  # type: ignore[union-attr]
    assert page.facet("label").get("low_performance").count == 35  # type: ignore[union-attr]
    assert page.facet("education").get("higher").count == 39  # type: ignore[union-attr]


def test_parser_discovers_role_id_from_cluster_url() -> None:
    page = HhVacancySearchResponseParser().parse(_fixture_payload())

    roles = {role.id: role.name for role in page.roles()}
    assert roles == {"96": "Программист, разработчик"}


def test_parser_fails_closed_when_clusters_disappear() -> None:
    payload = json.dumps({"found": 42, "items": []})

    with pytest.raises(HhParserContractBroken, match="no clusters"):
        HhVacancySearchResponseParser().parse(payload)


def test_parser_rejects_non_json_payload() -> None:
    with pytest.raises(HhParserContractBroken, match="cannot decode"):
        HhVacancySearchResponseParser().parse("<html>captcha</html>")


def test_parser_accepts_zero_result_with_empty_clusters() -> None:
    page = HhVacancySearchResponseParser().parse(
        json.dumps({"found": 0, "items": [], "clusters": []})
    )

    assert page.total_count == 0
    assert page.facets == ()
