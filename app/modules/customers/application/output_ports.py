from typing import Protocol

from app.modules.customers.infrastructure.models import Customer


class CustomerRepository(Protocol):
    async def get_by_phone(self, phone: str) -> Customer | None: ...
    async def add(self, customer: Customer) -> None: ...