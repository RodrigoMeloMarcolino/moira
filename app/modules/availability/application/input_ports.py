from datetime import date, datetime
from typing import Protocol
from uuid import UUID


class ProviderAvailableSlotsRetriever(Protocol):
    async def execute(
        self,
        provider_slug: str,
        offering_id: UUID,
        target_date: date,
    ) -> list[datetime]: ...
