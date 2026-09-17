import json

import pytest

from hhpulse.infrastructure.hh.errors import HhParserContractBroken
from hhpulse.infrastructure.hh.role_catalog import HhProfessionalRoleCatalogParser


def test_catalog_flattens_categories_and_deduplicates_role_ids() -> None:
    payload = json.dumps(
        {
            "categories": [
                {
                    "id": "1",
                    "roles": [
                        {"id": "96", "name": "Программист", "search_deprecated": False},
                        {"id": "160", "name": "DevOps-инженер"},
                    ],
                },
                {
                    "id": "2",
                    "roles": [
                        {"id": "96", "name": "Программист"},
                        {"id": "999", "name": "Старая роль", "search_deprecated": True},
                    ],
                },
            ]
        },
        ensure_ascii=False,
    )

    roles = HhProfessionalRoleCatalogParser().parse(payload)

    assert [(role.id, role.name) for role in roles] == [
        ("160", "DevOps-инженер"),
        ("96", "Программист"),
    ]


def test_catalog_fails_closed_on_conflicting_duplicate_role() -> None:
    payload = json.dumps(
        {
            "categories": [
                {"roles": [{"id": "96", "name": "Первое имя"}]},
                {"roles": [{"id": "96", "name": "Другое имя"}]},
            ]
        },
        ensure_ascii=False,
    )

    with pytest.raises(HhParserContractBroken, match="conflicting names"):
        HhProfessionalRoleCatalogParser().parse(payload)
