from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.infrastructure.models import User


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_id_by_email(self, email: str) -> Optional[UUID]:
        return await self.session.scalar(select(User.id).where(User.email == email))

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        return await self.session.scalar(select(User).where(User.email == email))

    async def add(self, user: User) -> None:
        self.session.add(user)
