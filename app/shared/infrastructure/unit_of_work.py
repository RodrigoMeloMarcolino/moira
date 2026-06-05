from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.application.exceptions import UnitOfWorkConflict


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            raise UnitOfWorkConflict from exc

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)
