from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

from hhpulse.domain.value_objects import FacetGroup, FacetOptionCount, ParsedSearchPage
from hhpulse.infrastructure.hh.errors import HhParserContractBroken


class HhVacancySearchResponseParser:
    """Strict parser for the documented JSON response of GET /vacancies."""

    def parse(self, raw_payload: str) -> ParsedSearchPage:
        payload = self._load_object(raw_payload)
        total_count = self._required_non_negative_int(payload, "found")
        raw_clusters = payload.get("clusters")
        if raw_clusters is None:
            raise HhParserContractBroken(
                "HH vacancy-search response has no clusters; expected clusters=true"
            )
        if not isinstance(raw_clusters, list):
            raise HhParserContractBroken("HH vacancy-search clusters are not a list")
        return ParsedSearchPage(
            total_count=total_count,
            facets=tuple(self._parse_group(group) for group in raw_clusters),
        )

    @staticmethod
    def _load_object(raw_payload: str) -> Mapping[str, Any]:
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise HhParserContractBroken(f"cannot decode HH vacancy-search JSON: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise HhParserContractBroken("HH vacancy-search payload is not an object")
        return payload

    @classmethod
    def _parse_group(cls, raw_group: Any) -> FacetGroup:
        if not isinstance(raw_group, Mapping):
            raise HhParserContractBroken("HH vacancy cluster group is not an object")
        key = str(raw_group.get("id", "")).strip()
        if not key:
            raise HhParserContractBroken("HH vacancy cluster group has no id")
        raw_items = raw_group.get("items")
        if not isinstance(raw_items, list):
            raise HhParserContractBroken(f"HH vacancy cluster {key!r} has no items list")

        options: dict[str, FacetOptionCount] = {}
        for raw_item in raw_items:
            option = cls._parse_item(key, raw_item)
            existing = options.get(option.id)
            if existing is not None and existing != option:
                raise HhParserContractBroken(
                    f"HH vacancy cluster {key!r} contains conflicting option {option.id!r}"
                )
            options[option.id] = option
        return FacetGroup(key=key, options=tuple(options.values()))

    @classmethod
    def _parse_item(cls, group_key: str, raw_item: Any) -> FacetOptionCount:
        if not isinstance(raw_item, Mapping):
            raise HhParserContractBroken(
                f"HH vacancy cluster {group_key!r} contains a non-object item"
            )
        title = str(raw_item.get("name", "")).strip()
        if not title:
            raise HhParserContractBroken(
                f"HH vacancy cluster {group_key!r} contains an item without a name"
            )
        count = cls._required_non_negative_int(raw_item, "count")
        raw_url = str(raw_item.get("url", "")).strip()
        if not raw_url:
            raise HhParserContractBroken(
                f"HH vacancy cluster {group_key!r} contains an item without a URL"
            )
        option_id = cls._option_id(group_key, raw_url)
        return FacetOptionCount(
            id=option_id,
            title=title,
            count=count,
            query=urlsplit(raw_url).query or None,
        )

    @staticmethod
    def _option_id(group_key: str, raw_url: str) -> str:
        query = parse_qs(urlsplit(raw_url).query, keep_blank_values=True)
        values = query.get(group_key)
        if values:
            value = values[-1].strip()
            if value:
                return value

        # A few cluster groups use a search parameter whose name differs from the
        # group id. These aliases are documented search parameters.
        aliases = {
            "salary": ("salary", "salary_mode"),
            "employment": ("employment", "employment_form"),
            "schedule": ("schedule", "work_schedule_by_days"),
        }
        for parameter in aliases.get(group_key, ()):
            values = query.get(parameter)
            if values and values[-1].strip():
                return values[-1].strip()

        # Unknown future groups remain usable instead of being thrown away. The
        # complete query string is stable enough to be an opaque option id and
        # known analytics facets never rely on this fallback.
        opaque = urlsplit(raw_url).query.strip()
        if opaque:
            return opaque
        raise HhParserContractBroken(
            f"cannot derive an option id for HH vacancy cluster {group_key!r}"
        )

    @staticmethod
    def _required_non_negative_int(payload: Mapping[str, Any], key: str) -> int:
        value = payload.get(key)
        if isinstance(value, bool):
            raise HhParserContractBroken(f"HH field {key!r} must be an integer")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise HhParserContractBroken(f"HH field {key!r} must be an integer") from exc
        if number < 0:
            raise HhParserContractBroken(f"HH field {key!r} must not be negative")
        return number
