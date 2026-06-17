from typing import Protocol
from uuid import UUID

from app.modules.availability.infrastructure.models import AvailabilityRule


class AvailabilityRuleRepository(Protocol):
    async def add(self, rule: AvailabilityRule) -> None: ...

    async def get_by_id(self, rule_id: UUID) -> AvailabilityRule | None: ...

    async def list_active_by_provider_and_weekday(
        self,
        provider_id: UUID,
        weekday: int,
    ) -> list[AvailabilityRule]: ...

    async def list_by_provider(
        self,
        provider_id: UUID,
    ) -> list[AvailabilityRule]: ...
