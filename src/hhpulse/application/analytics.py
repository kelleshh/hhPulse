from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import fmean, median, pstdev
from typing import Any

from hhpulse.application.ports.analytics import AnalyticsReadRepository, PublishedObservation
from hhpulse.domain.enums import ExperienceBand, RunStatus, SearchTarget
from hhpulse.domain.value_objects import ParsedSearchPage

METRIC_KEYS = {
    "hhIndex",
    "vacancies",
    "resumes",
    "lowResponseShare",
    "salaryVisibleShare",
    "remoteShare",
    "hybridShare",
    "higherEducationShare",
    "noExperienceShare",
}

SERIES_COLOURS = (
    "rgb(26, 68, 108)",
    "rgb(32, 91, 123)",
    "rgb(38, 115, 131)",
    "rgb(55, 139, 128)",
    "rgb(96, 158, 111)",
    "rgb(151, 170, 88)",
    "rgb(198, 163, 67)",
    "rgb(211, 126, 55)",
)


@dataclass(slots=True)
class _FacetOption:
    title: str
    count: int = 0


@dataclass(slots=True)
class _MarketRow:
    observation_date: date
    role_id: str
    role_name: str
    experience: ExperienceBand
    vacancies: int = 0
    resumes: int = 0
    vacancy_facets: dict[str, dict[str, _FacetOption]] = field(default_factory=dict)

    @property
    def hh_index(self) -> float | None:
        return self.resumes / self.vacancies if self.vacancies else None


class MarketAnalytics:
    def __init__(self, repository: AnalyticsReadRepository) -> None:
        self._repository = repository

    async def overview(self, *, metric: str, today: date) -> dict[str, Any]:
        self._validate_metric(metric)
        date_from = today - timedelta(days=29)
        observations = await self._repository.list_observations(
            date_from=date_from,
            date_to=today,
        )
        rows = self._aggregate(observations)
        runs = await self._repository.list_runs(date_from=date_from, date_to=today)
        dates = [date_from + timedelta(days=offset) for offset in range(30)]
        published_dates = {row.observation_date for row in rows}
        states: dict[date, str] = {item: "gap" for item in dates}
        for item in published_dates:
            states[item] = "published"
        for record in runs:
            run = record.run
            if run.status in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE, RunStatus.PLANNED}:
                states[run.observation_date] = "running"
            elif run.status is RunStatus.PARSER_BROKEN:
                states[run.observation_date] = "parser_broken"

        latest_date = max(published_dates, default=None)
        latest_rows = self._role_rows(rows, observation_date=latest_date) if latest_date else []
        leaders = sorted(latest_rows, key=lambda row: row.vacancies, reverse=True)[:8]
        primary_series = self._series(
            rows,
            metric=metric,
            selectors=[(row.role_id, ExperienceBand.ANY, row.role_name) for row in leaders],
            dates=sorted(published_dates),
        )
        latest_observations = sum(
            1
            for item in observations
            if latest_date is not None and item.observation.query.observation_date == latest_date
        )
        observation_days = []
        for item in dates:
            matching_runs = [record.run for record in runs if record.run.observation_date == item]
            active = next(
                (
                    run
                    for run in matching_runs
                    if run.status
                    in {RunStatus.RUNNING, RunStatus.WAITING_SOURCE, RunStatus.PLANNED}
                ),
                None,
            )
            observation_days.append(
                {
                    "date": item.isoformat(),
                    "state": states[item],
                    "completedUnits": active.completed_units if active else None,
                    "totalUnits": active.total_units if active else None,
                }
            )
        return {
            "observationDays": observation_days,
            "primarySeries": primary_series,
            "metric": metric,
            "publishedAt": max(
                (item.published_at for item in observations),
                default=None,
            ),
            "rolesObserved": len(latest_rows),
            "observations": latest_observations,
            "activeRun": None,
            "availability30d": len(published_dates) / 30,
        }

    async def comparison(
        self,
        *,
        metric: str,
        comparison_mode: str,
        role_ids: list[str],
        experience: str,
        experience_strata: list[str],
        date_from: date,
        date_to: date,
    ) -> list[dict[str, Any]]:
        self._validate_metric(metric)
        rows = self._aggregate(
            await self._repository.list_observations(date_from=date_from, date_to=date_to)
        )
        dates = sorted({row.observation_date for row in rows})
        if comparison_mode == "experience":
            if not role_ids:
                return []
            role_id = role_ids[0]
            role_name = next((row.role_name for row in rows if row.role_id == role_id), role_id)
            selectors = [
                (
                    role_id,
                    ExperienceBand(item),
                    f"{role_name} · {self._experience_label(ExperienceBand(item))}",
                )
                for item in experience_strata
            ]
        else:
            selected_experience = ExperienceBand(experience)
            selectors = [
                (
                    role_id,
                    selected_experience,
                    next((row.role_name for row in rows if row.role_id == role_id), role_id),
                )
                for role_id in role_ids
            ]
        return self._series(rows, metric=metric, selectors=selectors, dates=dates)

    async def snapshot(self, *, observation_date: date, role_id: str) -> dict[str, Any]:
        rows = self._aggregate(
            await self._repository.list_observations(
                date_from=observation_date,
                date_to=observation_date,
            )
        )
        row = next(
            (
                item
                for item in rows
                if item.observation_date == observation_date
                and item.role_id == role_id
                and item.experience is ExperienceBand.ANY
            ),
            None,
        )
        if row is None:
            raise KeyError("published snapshot not found")
        facet_payload = {
            key: self._distribution(options, denominator=row.vacancies)
            for key, options in row.vacancy_facets.items()
            if key != "professional_role"
        }
        return {
            "date": observation_date.isoformat(),
            "roleId": row.role_id,
            "roleName": row.role_name,
            **self._metric_payload(row),
            "distributions": {
                "experience": facet_payload.get("experience", []),
                "workFormat": facet_payload.get("work_format", []),
                "schedule": facet_payload.get("schedule", []),
                "employment": facet_payload.get("employment", []),
                "education": facet_payload.get("education", []),
                "labels": facet_payload.get("label", []),
            },
            "facets": facet_payload,
        }

    async def role_matrix(
        self,
        *,
        date_to: date,
        history_days: int = 90,
    ) -> dict[str, Any]:
        date_from = date_to - timedelta(days=max(1, min(history_days, 365)) - 1)
        rows = self._aggregate(
            await self._repository.list_observations(date_from=date_from, date_to=date_to)
        )
        available_dates = sorted({row.observation_date for row in rows})
        if not available_dates:
            return {
                "date": None,
                "availableDates": [],
                "rows": [],
                "statistics": {},
            }
        selected_date = max(item for item in available_dates if item <= date_to)
        latest_rows = self._role_rows(rows, observation_date=selected_date)
        payload_rows = []
        for row in latest_rows:
            history = [
                {
                    "date": item.observation_date.isoformat(),
                    **self._metric_payload(item),
                }
                for item in rows
                if item.role_id == row.role_id and item.experience is ExperienceBand.ANY
            ]
            payload_rows.append(
                {
                    "roleId": row.role_id,
                    "roleName": row.role_name,
                    **self._metric_payload(row),
                    "history": history,
                }
            )
        statistics = {
            metric: self._statistics(
                [value for item in latest_rows if (value := self._metric(item, metric)) is not None]
            )
            for metric in sorted(METRIC_KEYS)
        }
        return {
            "date": selected_date.isoformat(),
            "availableDates": [item.isoformat() for item in available_dates],
            "rows": payload_rows,
            "statistics": statistics,
        }

    async def alerts(self, *, today: date) -> list[dict[str, Any]]:
        runs = await self._repository.list_runs(
            date_from=today - timedelta(days=90),
            date_to=today,
        )
        resolved = await self._repository.list_resolved_alert_ids()
        result = []
        for record in reversed(runs):
            run = record.run
            if run.status not in {
                RunStatus.PARSER_BROKEN,
                RunStatus.FAILED,
                RunStatus.EXPIRED,
                RunStatus.WAITING_SOURCE,
            }:
                continue
            alert_id = f"run:{run.id}:{run.status.value}"
            severity = "critical" if run.status is RunStatus.PARSER_BROKEN else "warning"
            title = {
                RunStatus.PARSER_BROKEN: "Контракт HTML изменился",
                RunStatus.FAILED: "Сбор завершился ошибкой",
                RunStatus.EXPIRED: "Сбор не завершился до конца дня",
                RunStatus.WAITING_SOURCE: "Источник временно недоступен",
            }[run.status]
            occurred_at = run.finished_at or run.started_at
            result.append(
                {
                    "id": alert_id,
                    "severity": severity,
                    "title": title,
                    "description": run.error_message
                    or "Состояние зафиксировано в журнале запуска.",
                    "occurredAt": occurred_at.isoformat()
                    if occurred_at is not None
                    else f"{run.observation_date.isoformat()}T00:00:00+00:00",
                    "jobName": record.job_name,
                    "resolved": alert_id in resolved,
                }
            )
        return result

    @classmethod
    def _aggregate(
        cls,
        records: Sequence[PublishedObservation],
    ) -> list[_MarketRow]:
        deduplicated: dict[tuple[str, ...], PublishedObservation] = {}
        for record in records:
            query = record.observation.query
            observation_key = (
                query.observation_date.isoformat(),
                query.region_id,
                query.professional_role_id,
                query.experience.value,
                query.target.value,
            )
            deduplicated[observation_key] = record

        pairs: dict[
            tuple[date, str, str, ExperienceBand],
            dict[SearchTarget, ParsedSearchPage],
        ] = defaultdict(dict)
        for record in deduplicated.values():
            observation = record.observation
            query = observation.query
            query_key = (
                query.observation_date,
                query.region_id,
                query.professional_role_id,
                query.experience,
            )
            pairs[query_key][query.target] = observation.page

        aggregates: dict[tuple[date, str, ExperienceBand], _MarketRow] = {}
        for (observation_date, _region_id, role_id, experience), pages in pairs.items():
            vacancy = pages.get(SearchTarget.VACANCY)
            resume = pages.get(SearchTarget.RESUME)
            if vacancy is None or resume is None:
                continue
            aggregate_key = (observation_date, role_id, experience)
            row = aggregates.setdefault(
                aggregate_key,
                _MarketRow(
                    observation_date=observation_date,
                    role_id=role_id,
                    role_name=cls._role_name(role_id, vacancy, resume),
                    experience=experience,
                ),
            )
            row.vacancies += vacancy.total_count
            row.resumes += resume.total_count
            cls._merge_facets(row.vacancy_facets, vacancy)
        return sorted(
            aggregates.values(),
            key=lambda row: (row.observation_date, row.role_name.casefold(), row.experience.value),
        )

    @staticmethod
    def _merge_facets(target: dict[str, dict[str, _FacetOption]], page: ParsedSearchPage) -> None:
        for facet in page.facets:
            options = target.setdefault(facet.key, {})
            for option in facet.options:
                aggregate = options.setdefault(option.id, _FacetOption(title=option.title))
                aggregate.count += option.count

    @staticmethod
    def _role_name(role_id: str, *pages: ParsedSearchPage) -> str:
        for page in pages:
            facet = page.facet("professional_role")
            option = facet.get(role_id) if facet is not None else None
            if option is not None:
                return option.title
        return f"Профессия {role_id}"

    @classmethod
    def _metric_payload(cls, row: _MarketRow) -> dict[str, float | int | None]:
        return {metric: cls._metric(row, metric) for metric in METRIC_KEYS}

    @classmethod
    def _metric(cls, row: _MarketRow, metric: str) -> float | int | None:
        if metric == "hhIndex":
            return row.hh_index
        if metric == "vacancies":
            return row.vacancies
        if metric == "resumes":
            return row.resumes
        mapping = {
            "lowResponseShare": ("label", "low_performance"),
            "salaryVisibleShare": ("label", "with_salary"),
            "remoteShare": ("work_format", "REMOTE"),
            "hybridShare": ("work_format", "HYBRID"),
            "higherEducationShare": ("education", "higher"),
            "noExperienceShare": ("experience", "noExperience"),
        }
        facet_key, option_id = mapping[metric]
        option = row.vacancy_facets.get(facet_key, {}).get(option_id)
        if option is None or row.vacancies == 0:
            return None
        return option.count / row.vacancies

    @classmethod
    def _series(
        cls,
        rows: list[_MarketRow],
        *,
        metric: str,
        selectors: list[tuple[str, ExperienceBand, str]],
        dates: list[date],
    ) -> list[dict[str, Any]]:
        index = {(row.observation_date, row.role_id, row.experience): row for row in rows}
        result = []
        for position, (role_id, experience, label) in enumerate(selectors):
            series_id = (
                role_id if experience is ExperienceBand.ANY else f"{role_id}:{experience.value}"
            )
            result.append(
                {
                    "id": series_id,
                    "label": label,
                    "colour": SERIES_COLOURS[position % len(SERIES_COLOURS)],
                    "points": [
                        {
                            "date": item.isoformat(),
                            "value": cls._metric(row, metric)
                            if (row := index.get((item, role_id, experience)))
                            else None,
                        }
                        for item in dates
                    ],
                }
            )
        return result

    @staticmethod
    def _distribution(
        options: dict[str, _FacetOption],
        *,
        denominator: int,
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": option_id,
                "label": option.title,
                "value": option.count,
                "share": option.count / denominator if denominator else 0,
            }
            for option_id, option in sorted(
                options.items(),
                key=lambda item: (-item[1].count, item[1].title.casefold()),
            )
        ]

    @staticmethod
    def _statistics(values: list[float | int]) -> dict[str, float | int | None]:
        numeric = sorted(float(value) for value in values if math.isfinite(float(value)))
        if not numeric:
            return {
                "count": 0,
                "min": None,
                "q1": None,
                "median": None,
                "q3": None,
                "max": None,
                "mean": None,
                "stddev": None,
            }

        def quantile(fraction: float) -> float:
            position = (len(numeric) - 1) * fraction
            lower = math.floor(position)
            upper = math.ceil(position)
            if lower == upper:
                return numeric[lower]
            return numeric[lower] + (numeric[upper] - numeric[lower]) * (position - lower)

        return {
            "count": len(numeric),
            "min": numeric[0],
            "q1": quantile(0.25),
            "median": median(numeric),
            "q3": quantile(0.75),
            "max": numeric[-1],
            "mean": fmean(numeric),
            "stddev": pstdev(numeric),
        }

    @staticmethod
    def _role_rows(rows: list[_MarketRow], *, observation_date: date | None) -> list[_MarketRow]:
        if observation_date is None:
            return []
        return [
            row
            for row in rows
            if row.observation_date == observation_date and row.experience is ExperienceBand.ANY
        ]

    @staticmethod
    def _experience_label(experience: ExperienceBand) -> str:
        return {
            ExperienceBand.ANY: "Любой опыт",
            ExperienceBand.NO_EXPERIENCE: "Без опыта",
            ExperienceBand.BETWEEN_1_AND_3: "1–3 года",
            ExperienceBand.BETWEEN_3_AND_6: "3–6 лет",
            ExperienceBand.MORE_THAN_6: "Более 6 лет",
        }[experience]

    @staticmethod
    def _validate_metric(metric: str) -> None:
        if metric not in METRIC_KEYS:
            raise ValueError(f"unsupported metric: {metric}")
