from typing import Optional, Protocol

from app.modules.customers.infrastructure.models import Customer


class CustomerRepository(Protocol):
    async def get_by_phone(self, phone: str) -> Optional[Customer]: ...
    async def add(self, customer: Customer) -> None: ...
