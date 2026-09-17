from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from hhpulse.domain.entities import AnalysisScope, CrawlRun
from hhpulse.domain.enums import RoleSelectionMode, RunStatus
from hhpulse.domain.errors import DomainError, InvalidStateTransition

MOSCOW = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=MOSCOW)


def test_selected_scope_requires_roles() -> None:
    with pytest.raises(DomainError, match="requires at least one role"):
        AnalysisScope(
            region_ids=("1",),
            role_selection_mode=RoleSelectionMode.SELECTED,
            role_ids=(),
        )


def test_all_roles_scope_rejects_explicit_roles() -> None:
    with pytest.raises(DomainError, match="must not contain explicit role"):
        AnalysisScope(
            region_ids=("1",),
            role_selection_mode=RoleSelectionMode.ALL,
            role_ids=("96",),
        )


def test_run_cannot_publish_partial_result() -> None:
    run = CrawlRun(id="run-1", job_id="job-1", observation_date=date(2026, 9, 17))
    run = run.start(total_units=2, at=NOW).mark_unit_completed()

    with pytest.raises(InvalidStateTransition, match="incomplete"):
        run.succeed(at=NOW)


def test_run_waits_and_resumes_without_losing_progress() -> None:
    run = CrawlRun(id="run-1", job_id="job-1", observation_date=date(2026, 9, 17))
    run = run.start(total_units=2, at=NOW).mark_unit_completed().wait_for_source()
    resumed = run.resume()

    assert resumed.status is RunStatus.RUNNING
    assert resumed.completed_units == 1


def test_parser_break_is_terminal_failure_kind() -> None:
    run = CrawlRun(id="run-1", job_id="job-1", observation_date=date(2026, 9, 17))
    broken = run.start(total_units=1, at=NOW).parser_broken(message="missing clusters", at=NOW)

    assert broken.status is RunStatus.PARSER_BROKEN
    assert broken.error_code == "PARSER_CONTRACT_BROKEN"
    with pytest.raises(InvalidStateTransition):
        broken.fail(code="OTHER", message="must stay parser-broken", at=NOW)


def test_run_can_expire_without_losing_progress() -> None:
    run = CrawlRun(id="run-1", job_id="job-1", observation_date=date(2026, 9, 17))
    run = run.start(total_units=3, at=NOW).mark_unit_completed().wait_for_source()

    expired = run.expire(at=NOW)

    assert expired.status is RunStatus.EXPIRED
    assert expired.completed_units == 1
    assert expired.error_code == "DAY_EXPIRED"
