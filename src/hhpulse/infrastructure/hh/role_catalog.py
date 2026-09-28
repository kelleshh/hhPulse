from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from hhpulse.domain.value_objects import ProfessionalRole
from hhpulse.infrastructure.hh.errors import HhParserContractBroken


class HhProfessionalRoleCatalogParser:
    def parse(self, raw_payload: str) -> tuple[ProfessionalRole, ...]:
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise HhParserContractBroken(
                f"cannot decode HH professional-role catalog: {exc}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise HhParserContractBroken("HH professional-role catalog is not an object")
        categories = payload.get("categories")
        if not isinstance(categories, list) or not categories:
            raise HhParserContractBroken("HH professional-role catalog has no categories")

        roles: dict[str, ProfessionalRole] = {}
        for category in categories:
            self._collect_category(category, roles)
        if not roles:
            raise HhParserContractBroken("HH professional-role catalog contains no active roles")
        return tuple(sorted(roles.values(), key=lambda role: role.id))

    @staticmethod
    def _collect_category(
        category: Any,
        roles: dict[str, ProfessionalRole],
    ) -> None:
        if not isinstance(category, Mapping):
            raise HhParserContractBroken("HH professional-role category is not an object")
        raw_roles = category.get("roles")
        if not isinstance(raw_roles, list):
            raise HhParserContractBroken("HH professional-role category has no roles list")
        for raw_role in raw_roles:
            HhProfessionalRoleCatalogParser._collect_role(raw_role, roles)

    @staticmethod
    def _collect_role(raw_role: Any, roles: dict[str, ProfessionalRole]) -> None:
        if not isinstance(raw_role, Mapping):
            raise HhParserContractBroken("HH professional role is not an object")
        if raw_role.get("search_deprecated") is True:
            return
        role_id = str(raw_role.get("id", "")).strip()
        name = str(raw_role.get("name", "")).strip()
        if not role_id or not name:
            raise HhParserContractBroken("HH professional role has empty id or name")
        role = ProfessionalRole(id=role_id, name=name)
        existing = roles.get(role_id)
        if existing is not None and existing.name != role.name:
            raise HhParserContractBroken(f"HH professional role {role_id!r} has conflicting names")
        roles[role_id] = role
