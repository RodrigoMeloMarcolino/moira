from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.availability.infrastructure.models import AvailabilityRule


class SQLAlchemyAvailabilityRulesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, rule: AvailabilityRule) -> None:
        self.session.add(rule)

    async def get_by_id(self, rule_id: UUID) -> Optional[AvailabilityRule]:
        return await self.session.get(AvailabilityRule, rule_id)

    async def list_active_by_provider_and_weekday(
        self,
        provider_id: UUID,
        weekday: int,
    ) -> list[AvailabilityRule]:
        result = await self.session.scalars(
            select(AvailabilityRule).where(
                AvailabilityRule.provider_id == provider_id,
                AvailabilityRule.weekday == weekday,
                AvailabilityRule.is_active.is_(True),
            )
        )

        return list(result)

    async def list_by_provider(self, provider_id: UUID) -> list[AvailabilityRule]:
        result = await self.session.scalars(
            select(AvailabilityRule).where(AvailabilityRule.provider_id == provider_id)
        )

        return list(result)
