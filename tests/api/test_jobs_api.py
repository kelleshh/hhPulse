from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from hhpulse.api.app import create_app
from hhpulse.bootstrap import Container
from hhpulse.config import Settings
from hhpulse.domain.entities import AnalysisJob


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

    async def delete(self, job_id: str) -> bool:
        return self.items.pop(job_id, None) is not None


class UnusedExecutions:
    async def get_for_job_date(self, job_id, observation_date):
        return None


class FakeScheduler:
    def __init__(self) -> None:
        self.triggers: list[str] = []
        self.cancelled: list[str] = []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def trigger(self, job_id: str) -> bool:
        self.triggers.append(job_id)
        return True

    async def cancel(self, job_id: str) -> None:
        self.cancelled.append(job_id)


def _client(*, scheduler=None) -> TestClient:
    container = Container(
        settings=Settings(db_path=":memory:"),
        clock=FakeClock(),
        jobs=InMemoryJobs(),
        executions=UnusedExecutions(),
        scheduler=scheduler,
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


def test_manual_run_endpoint_delegates_to_scheduler() -> None:
    scheduler = FakeScheduler()
    with _client(scheduler=scheduler) as client:
        created = client.post(
            "/api/v1/jobs",
            json={"name": "Москва", "region_ids": ["1"]},
        ).json()
        response = client.post(f"/api/v1/jobs/{created['id']}/runs/today")

    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    assert scheduler.triggers == [created["id"]]


def test_delete_job_cancels_active_work_and_removes_job() -> None:
    scheduler = FakeScheduler()
    with _client(scheduler=scheduler) as client:
        created = client.post(
            "/api/v1/jobs",
            json={"name": "Москва", "region_ids": ["1"]},
        ).json()
        response = client.delete(f"/api/v1/jobs/{created['id']}")
        listed = client.get("/api/v1/jobs")

    assert response.status_code == 204
    assert response.content == b""
    assert listed.json() == []
    assert scheduler.cancelled == [created["id"]]


def test_delete_missing_job_returns_404() -> None:
    with _client() as client:
        response = client.delete("/api/v1/jobs/missing")
    assert response.status_code == 404
