from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from hhpulse.api.app import create_app
from hhpulse.bootstrap import Container
from hhpulse.config import Settings
from hhpulse.domain.entities import AnalysisJob, CrawlRun


class FakeClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 17, 12, 30, tzinfo=ZoneInfo("Europe/Moscow"))

    def today(self) -> date:
        return self.now().date()


class InMemoryJobs:
    def __init__(self) -> None:
        self.items: dict[str, AnalysisJob] = {}

    async def add(self, job: AnalysisJob) -> None:
        self.items[job.id] = job

    async def get(self, job_id: str) -> AnalysisJob | None:
        return self.items.get(job_id)

    async def list(self) -> tuple[AnalysisJob, ...]:
        return tuple(self.items.values())

    async def update(self, job: AnalysisJob) -> None:
        self.items[job.id] = job


class InMemoryRuns:
    async def add(self, run: CrawlRun) -> None:
        return None

    async def get(self, run_id: str) -> CrawlRun | None:
        return None

    async def get_for_job_date(self, job_id: str, observation_date: date) -> CrawlRun | None:
        return None

    async def update(self, run: CrawlRun) -> None:
        return None


class InMemoryUnits:
    async def add_many(self, units):
        return None

    async def list_for_run(self, run_id: str):
        return ()

    async def list_incomplete_for_run(self, run_id: str):
        return ()

    async def update(self, unit):
        return None


class InMemoryObservations:
    async def stage(self, run_id: str, unit_id: str, observation):
        return None

    async def publish_run(self, run_id: str):
        return None

    async def discard_staging(self, run_id: str):
        return None


def _client() -> TestClient:
    container = Container(
        settings=Settings(db_path=":memory:"),
        clock=FakeClock(),
        jobs=InMemoryJobs(),
        runs=InMemoryRuns(),
        units=InMemoryUnits(),
        observations=InMemoryObservations(),
    )
    return TestClient(create_app(container=container))


def test_create_list_and_disable_job() -> None:
    with _client() as client:
        response = client.post(
            "/api/v1/jobs",
            json={
                "name": "Москва — все роли",
                "region_ids": ["1"],
                "role_selection_mode": "all",
                "role_ids": [],
                "max_concurrency": 1,
                "max_rps": 0.5,
                "user_agent_mode": "shared",
            },
        )
        assert response.status_code == 201
        created = response.json()
        assert created["active_resume_window_days"] == 60
        assert created["enabled"] is True

        listed = client.get("/api/v1/jobs")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        disabled = client.patch(
            f"/api/v1/jobs/{created['id']}/enabled",
            json={"enabled": False},
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False


def test_all_role_mode_rejects_explicit_role_ids() -> None:
    with _client() as client:
        response = client.post(
            "/api/v1/jobs",
            json={
                "name": "broken",
                "region_ids": ["1"],
                "role_selection_mode": "all",
                "role_ids": ["96"],
            },
        )
        assert response.status_code == 422
        assert "must not contain explicit role" in response.json()["detail"]
