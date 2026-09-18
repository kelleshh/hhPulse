from __future__ import annotations

import json
from datetime import date
from typing import Any

from hhpulse.domain.enums import ExperienceBand, SearchTarget
from hhpulse.domain.value_objects import (
    FacetGroup,
    FacetOptionCount,
    ParsedSearchPage,
    QueryFilter,
    SearchObservation,
    SearchQuery,
)


def query_to_json(query: SearchQuery) -> str:
    payload = {
        "target": query.target.value,
        "observation_date": query.observation_date.isoformat(),
        "region_id": query.region_id,
        "professional_role_id": query.professional_role_id,
        "experience": query.experience.value,
        "extra_filters": [
            {"key": item.key, "values": list(item.values)} for item in query.extra_filters
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def query_from_json(raw: str) -> SearchQuery:
    payload = _load_object(raw)
    return SearchQuery(
        target=SearchTarget(str(payload["target"])),
        observation_date=date.fromisoformat(str(payload["observation_date"])),
        region_id=str(payload["region_id"]),
        professional_role_id=str(payload["professional_role_id"]),
        experience=ExperienceBand(str(payload["experience"])),
        extra_filters=tuple(
            QueryFilter(
                key=str(item["key"]),
                values=tuple(str(value) for value in item["values"]),
            )
            for item in payload.get("extra_filters", [])
        ),
    )


def observation_to_json(observation: SearchObservation) -> str:
    payload = {
        "query": json.loads(query_to_json(observation.query)),
        "page": {
            "total_count": observation.page.total_count,
            "facets": [
                {
                    "key": facet.key,
                    "options": [
                        {
                            "id": option.id,
                            "title": option.title,
                            "count": option.count,
                            "query": option.query,
                            "disabled": option.disabled,
                        }
                        for option in facet.options
                    ],
                }
                for facet in observation.page.facets
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def observation_from_json(raw: str) -> SearchObservation:
    payload = _load_object(raw)
    query = query_from_json(json.dumps(payload["query"], ensure_ascii=False))
    page_payload = payload["page"]
    if not isinstance(page_payload, dict):
        raise ValueError("observation page must be an object")
    facets_payload = page_payload.get("facets", [])
    return SearchObservation(
        query=query,
        page=ParsedSearchPage(
            total_count=int(page_payload["total_count"]),
            facets=tuple(
                FacetGroup(
                    key=str(facet["key"]),
                    options=tuple(
                        FacetOptionCount(
                            id=str(option["id"]),
                            title=str(option["title"]),
                            count=int(option["count"]),
                            query=(
                                str(option["query"]) if option.get("query") is not None else None
                            ),
                            disabled=bool(option.get("disabled", False)),
                        )
                        for option in facet.get("options", [])
                    ),
                )
                for facet in facets_payload
            ),
        ),
    )


def _load_object(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("serialized payload must be a JSON object")
    return payload
