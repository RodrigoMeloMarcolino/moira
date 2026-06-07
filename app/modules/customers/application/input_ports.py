from typing import Protocol

from app.modules.customers.infrastructure.models import Customer
from app.modules.customers.schemas.customer import CustomerGetOrCreateByPhone


class CustomerCreatorGetter(Protocol):
    async def execute(self, payload: CustomerGetOrCreateByPhone) -> Customer: ...