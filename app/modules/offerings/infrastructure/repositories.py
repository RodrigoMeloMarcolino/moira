from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offerings.infrastructure.models import Offering


class SqlAlchemyOfferingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, offering_id: UUID) -> Offering | None:
        return await self.session.get(Offering, offering_id)

    async def list_active_by_provider_id(self, provider_id: UUID) -> list[Offering]:
        result = await self.session.scalars(
            select(Offering)
            .where(Offering.provider_id == provider_id, Offering.is_active.is_(True))
            .order_by(Offering.title)
        )

        return list(result)

    async def list_by_provider_id(self, provider_id: UUID) -> list[Offering]:
        result = await self.session.scalars(
            select(Offering)
            .where(Offering.provider_id == provider_id)
            .order_by(Offering.title)
        )

        return list(result)

    async def add(self, offering: Offering) -> None:
        self.session.add(offering)

    async def get_active_by_id(self, offering_id: UUID) -> Offering | None:
        return await self.session.scalar(
            select(Offering).where(
                Offering.id == offering_id, Offering.is_active.is_(True)
            )
        )
