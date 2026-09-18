from __future__ import annotations

import html as html_module
import json
import re
from collections.abc import Mapping
from typing import Any

from bs4 import BeautifulSoup

from hhpulse.domain.value_objects import FacetGroup, FacetOptionCount, ParsedSearchPage
from hhpulse.infrastructure.hh.errors import HhParserContractBroken

_TOTAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Найден[оа]\s+([\d\s\u00a0\u202f]+)\s+ваканс", re.IGNORECASE),
    re.compile(r"Найден[оа]\s+([\d\s\u00a0\u202f]+)\s+резюм", re.IGNORECASE),
)

_ZERO_RESULT_TITLES = frozenset(
    {
        "по запросу ничего не найдено",
        "по вашему запросу ничего не найдено",
        "ничего не нашлось",
    }
)


class HhSearchPageParser:
    """Parses only aggregate counts already embedded in HH search HTML.

    The parser deliberately ignores individual vacancies/resumes. Its contract is:
    a numeric search total plus the server-rendered ``searchClusters`` object.
    """

    def parse(self, raw_html: str) -> ParsedSearchPage:
        if not raw_html.strip():
            raise HhParserContractBroken("HH returned an empty HTML document")
        decoded_html = html_module.unescape(raw_html)
        total_count = self._parse_total(decoded_html)
        clusters = self._extract_named_json_object(decoded_html, "searchClusters")
        facets = self._parse_facets(clusters)

        if not facets:
            raise HhParserContractBroken("searchClusters contains no countable facet groups")
        return ParsedSearchPage(total_count=total_count, facets=facets)

    def _parse_total(self, decoded_html: str) -> int:
        soup = BeautifulSoup(decoded_html, "html.parser")
        visible_text = soup.get_text(" ", strip=True)
        for pattern in _TOTAL_PATTERNS:
            match = pattern.search(visible_text)
            if match is not None:
                return self._parse_int(match.group(1))

        # HH renders a semantic empty-result title instead of ``Найдено 0``.
        # Restrict the check to visible heading nodes so translation dictionaries
        # embedded in scripts/templates cannot turn an unrelated page into zero.
        for heading in soup.select("h1[data-qa='title'], h2[data-qa='title']"):
            normalized = " ".join(heading.get_text(" ", strip=True).lower().split())
            if normalized in _ZERO_RESULT_TITLES:
                return 0

        # Fallback: the actual result header can be present inside server state markup.
        for pattern in _TOTAL_PATTERNS:
            match = pattern.search(decoded_html)
            if match is not None:
                return self._parse_int(match.group(1))
        raise HhParserContractBroken("cannot find a numeric HH search total")

    @staticmethod
    def _parse_int(value: str) -> int:
        digits = re.sub(r"\D", "", value)
        if not digits:
            raise HhParserContractBroken(f"cannot parse integer from {value!r}")
        return int(digits)

    @staticmethod
    def _extract_named_json_object(document: str, key: str) -> Mapping[str, Any]:
        marker = f'"{key}"'
        decoder = json.JSONDecoder()
        search_from = 0
        errors: list[str] = []

        while True:
            marker_index = document.find(marker, search_from)
            if marker_index < 0:
                break
            colon_index = document.find(":", marker_index + len(marker))
            if colon_index < 0:
                break
            object_index = document.find("{", colon_index + 1)
            if object_index < 0:
                break
            try:
                parsed, _ = decoder.raw_decode(document[object_index:])
            except json.JSONDecodeError as exc:
                errors.append(str(exc))
                search_from = marker_index + len(marker)
                continue
            if isinstance(parsed, Mapping):
                return parsed
            search_from = marker_index + len(marker)

        details = f"; decoder errors: {errors[-2:]}" if errors else ""
        raise HhParserContractBroken(f"cannot decode {key} from HH HTML{details}")

    @staticmethod
    def _parse_facets(clusters: Mapping[str, Any]) -> tuple[FacetGroup, ...]:
        result: list[FacetGroup] = []
        for facet_key, facet_payload in clusters.items():
            if not isinstance(facet_payload, Mapping):
                continue
            groups = facet_payload.get("groups")
            if not isinstance(groups, Mapping):
                continue

            options: list[FacetOptionCount] = []
            for fallback_id, option_payload in groups.items():
                if not isinstance(option_payload, Mapping):
                    continue
                raw_count = option_payload.get("count")
                if not isinstance(raw_count, int) or raw_count < 0:
                    continue
                option_id = str(option_payload.get("id", fallback_id)).strip()
                title = str(option_payload.get("title", option_id)).replace("\u00a0", " ").strip()
                if not option_id or not title:
                    continue
                query = option_payload.get("query")
                options.append(
                    FacetOptionCount(
                        id=option_id,
                        title=title,
                        count=raw_count,
                        query=str(query) if query is not None else None,
                        disabled=bool(option_payload.get("disabled", False)),
                    )
                )

            if options:
                result.append(FacetGroup(key=str(facet_key), options=tuple(options)))

        return tuple(result)
