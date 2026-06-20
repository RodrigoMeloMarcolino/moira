from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.providers.infrastructure.models import Provider


class SqlAlchemyProviderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_id_by_slug(self, slug: str) -> Optional[UUID]:
        return await self.session.scalar(
            select(Provider.id).where(Provider.slug == slug)
        )

    async def get_by_id(self, provider_id: UUID) -> Optional[Provider]:
        return await self.session.get(Provider, provider_id)

    async def get_by_user_id(self, user_id: UUID) -> Optional[Provider]:
        return await self.session.scalar(
            select(Provider).where(Provider.user_id == user_id)
        )

    async def get_by_slug(self, slug: str) -> Optional[Provider]:
        return await self.session.scalar(select(Provider).where(Provider.slug == slug))

    async def add(self, provider: Provider) -> None:
        self.session.add(provider)
