import html
import json

import pytest

from hhpulse.infrastructure.hh.errors import HhParserContractBroken
from hhpulse.infrastructure.hh.parser import HhSearchPageParser


def _fixture_html() -> str:
    state = {
        "searchClusters": {
            "experience": {
                "groups": {
                    "noExperience": {
                        "count": 5,
                        "query": "experience=noExperience",
                        "disabled": False,
                        "title": "Нет опыта",
                        "id": "noExperience",
                    },
                    "between1And3": {
                        "count": 39,
                        "query": "experience=between1And3",
                        "disabled": False,
                        "title": "От 1 года до 3 лет",
                        "id": "between1And3",
                    },
                }
            },
            "education": {
                "groups": {
                    "higher": {
                        "count": 39,
                        "query": "education=higher",
                        "disabled": False,
                        "title": "Высшее",
                        "id": "higher",
                    }
                }
            },
            "work_format": {
                "groups": {
                    "ON_SITE": {"count": 137, "title": "На месте работодателя", "id": "ON_SITE"},
                    "HYBRID": {"count": 39, "title": "Гибрид", "id": "HYBRID"},
                    "REMOTE": {"count": 28, "title": "Удалённо", "id": "REMOTE"},
                }
            },
            "label": {
                "groups": {
                    "with_salary": {
                        "count": 8,
                        "query": "label=with_salary",
                        "title": "Указан доход",
                        "id": "with_salary",
                    },
                    "low_performance": {
                        "count": 35,
                        "query": "label=low_performance",
                        "title": "Меньше 10 откликов",
                        "id": "low_performance",
                    },
                }
            },
            "professional_role": {
                "groups": {
                    "96": {"count": 100, "title": "Программист, разработчик", "id": "96"},
                    "160": {"count": 42, "title": "DevOps-инженер", "id": "160"},
                }
            },
        }
    }
    encoded_state = html.escape(json.dumps(state, ensure_ascii=False), quote=True)
    return f"""
    <!doctype html>
    <html><body>
      <h1 data-qa="vacancies-search-header">Найдено 1 234 вакансии</h1>
      <template>{encoded_state}</template>
    </body></html>
    """


def test_parser_extracts_total_and_all_server_facets() -> None:
    page = HhSearchPageParser().parse(_fixture_html())

    assert page.total_count == 1234
    assert page.facet("work_format").get("REMOTE").count == 28  # type: ignore[union-attr]
    assert page.facet("label").get("low_performance").count == 35  # type: ignore[union-attr]
    assert page.facet("education").get("higher").count == 39  # type: ignore[union-attr]


def test_parser_discovers_roles_from_professional_role_facet() -> None:
    page = HhSearchPageParser().parse(_fixture_html())

    roles = {role.id: role.name for role in page.roles()}
    assert roles == {"96": "Программист, разработчик", "160": "DevOps-инженер"}


def test_parser_fails_closed_when_clusters_disappear() -> None:
    html_page = "<html><body><h1>Найдено 42 вакансии</h1></body></html>"

    with pytest.raises(HhParserContractBroken, match="searchClusters"):
        HhSearchPageParser().parse(html_page)


def test_parser_rejects_non_search_page_by_semantic_contract() -> None:
    with pytest.raises(HhParserContractBroken, match="numeric HH search total"):
        HhSearchPageParser().parse("<html>DDoS-Guard js-challenge captcha</html>")


def test_parser_accepts_explicit_zero_result_page() -> None:
    state = {
        "searchClusters": {
            "experience": {
                "groups": {
                    "moreThan6": {
                        "count": 0,
                        "title": "Более 6 лет",
                        "id": "moreThan6",
                    }
                }
            }
        }
    }
    encoded_state = html.escape(json.dumps(state, ensure_ascii=False), quote=True)
    html_page = f"""
    <html><body>
      <h1 data-qa="title">По запросу ничего не найдено</h1>
      <h2 data-qa="title">Ничего не нашлось</h2>
      <template>{encoded_state}</template>
    </body></html>
    """

    page = HhSearchPageParser().parse(html_page)

    assert page.total_count == 0
    assert page.facet("experience").get("moreThan6").count == 0  # type: ignore[union-attr]


def test_parser_does_not_accept_zero_phrase_outside_a_result_heading() -> None:
    html_page = """
    <html><body>
      <script>window.translations = {"empty": "Ничего не нашлось"}</script>
    </body></html>
    """

    with pytest.raises(HhParserContractBroken, match="numeric HH search total"):
        HhSearchPageParser().parse(html_page)
