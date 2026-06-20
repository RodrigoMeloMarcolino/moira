from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.customers.infrastructure.models import Customer


class SQLAlchemyCustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_phone(self, phone: str) -> Optional[Customer]:
        return await self.session.scalar(
            select(Customer).where(Customer.phone == phone)
        )

    async def add(self, customer: Customer) -> None:
        self.session.add(customer)
