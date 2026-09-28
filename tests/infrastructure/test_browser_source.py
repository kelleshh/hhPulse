from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from hhpulse.application.errors import MarketSourceRejected, ParserContractBroken
from hhpulse.domain.entities import AnalysisJob, AnalysisScope
from hhpulse.domain.enums import ExperienceBand, RoleSelectionMode, SearchTarget, UserAgentMode
from hhpulse.domain.value_objects import (
    DailySchedule,
    Methodology,
    ProfessionalRole,
    RateLimitPolicy,
    SearchQuery,
)
from hhpulse.infrastructure.browser.source import BrowserMarketSource, search_url


class Catalog:
    async def list_roles(self):
        return (ProfessionalRole("96", "Разработчик"), ProfessionalRole("160", "DevOps"))


class Bridge:
    connected = True

    def __init__(self, result):
        self.result = result
        self.url = ""

    async def request(self, *, url, target, timeout_seconds):
        self.url = url
        return {"url": url, **self.result}


def job():
    now = datetime(2026, 9, 28, tzinfo=ZoneInfo("Europe/Moscow"))
    return AnalysisJob(
        "job",
        "Москва",
        AnalysisScope(("1",), RoleSelectionMode.ALL),
        RateLimitPolicy(),
        UserAgentMode.SHARED,
        DailySchedule(),
        Methodology(),
        True,
        now,
        now,
    )


def query(target, role="*", experience=ExperienceBand.ANY):
    return SearchQuery(target, date(2026, 9, 28), "1", role, experience)


async def test_resume_uses_full_count_and_fixes_60_day_window():
    bridge = Bridge({"status": "ok", "total": 2123, "visible": 151, "hidden": 1972})
    source = BrowserMarketSource(bridge, Catalog(), job())
    await source.discover_roles(region_id="1")
    page = await source.fetch(query(SearchTarget.RESUME, "96"))
    assert page.total_count == 2123
    assert page.facet("professional_role").get("96").count == 2123
    assert "date_from=31.07.2026" in bridge.url
    assert "date_to=28.09.2026" in bridge.url
    assert bridge.url.count("job_search_status=") == 3


async def test_hidden_resumes_are_never_assigned_to_a_different_filtered_search():
    bridge = Bridge({"status": "ok", "total": 2123, "visible": 151, "hidden": 100})
    source = BrowserMarketSource(bridge, Catalog(), job())
    await source.discover_roles(region_id="1")
    with pytest.raises(ParserContractBroken, match=r"visible.*hidden"):
        await source.fetch(query(SearchTarget.RESUME, "96"))


async def test_complete_vacancy_tree_yields_each_profession_once():
    bridge = Bridge(
        {
            "status": "ok",
            "total": 300,
            "tree_complete": True,
            "roles": [
                {"id": "96", "name": "Разработчик", "count": 20},
                {"id": "160", "name": "DevOps", "count": 10},
            ],
        }
    )
    source = BrowserMarketSource(bridge, Catalog(), job())
    await source.discover_roles(region_id="1")
    page = await source.fetch(query(SearchTarget.VACANCY))
    assert {role.id: role.count for role in page.facet("professional_role").options} == {
        "96": 20,
        "160": 10,
    }
    assert "professional_role=" not in bridge.url


async def test_incomplete_tree_or_block_never_publishes_a_count():
    bridge = Bridge({"status": "ok", "total": 300, "tree_complete": False, "roles": []})
    source = BrowserMarketSource(bridge, Catalog(), job())
    await source.discover_roles(region_id="1")
    with pytest.raises(ParserContractBroken):
        await source.fetch(query(SearchTarget.VACANCY))
    bridge.result = {"status": "blocked", "reason": "too many requests"}
    with pytest.raises(MarketSourceRejected):
        await source.fetch(query(SearchTarget.VACANCY))


async def test_new_profession_not_in_fallback_catalog_aborts_all_roles_run():
    bridge = Bridge(
        {
            "status": "ok",
            "total": 10,
            "tree_complete": True,
            "roles": [{"id": "99999", "name": "Новая роль", "count": 10}],
        }
    )
    source = BrowserMarketSource(bridge, Catalog(), job())
    await source.discover_roles(region_id="1")
    with pytest.raises(ParserContractBroken, match="new role IDs"):
        await source.fetch(query(SearchTarget.VACANCY))


def test_remote_region_and_experience_use_russian_population():
    item = SearchQuery(
        SearchTarget.RESUME, date(2026, 9, 28), "remote", "96", ExperienceBand.BETWEEN_1_AND_3
    )
    url = search_url(item)
    assert "area=113" in url and "work_format=REMOTE" in url
    assert "experience=between1And3" in url
