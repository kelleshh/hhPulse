from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from hhpulse.domain.value_objects import ProfessionalRole


class ProfessionalRoleCatalog(Protocol):
    async def list_roles(self) -> Sequence[ProfessionalRole]: ...
