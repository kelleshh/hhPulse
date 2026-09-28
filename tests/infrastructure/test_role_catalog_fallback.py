import requests

from hhpulse.infrastructure.hh.catalog import HhProfessionalRoleCatalog


async def test_unregistered_public_catalog_failure_uses_supplied_role_snapshot(monkeypatch):
    catalog = HhProfessionalRoleCatalog()

    def offline():
        raise requests.HTTPError("403")

    monkeypatch.setattr(catalog, "_fetch", offline)
    roles = await catalog.list_roles()
    assert len(roles) == 194
    assert {role.id for role in roles} >= {"96", "160"}
