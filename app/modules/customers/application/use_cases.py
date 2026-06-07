
from app.modules.customers.application.output_ports import CustomerRepository
from app.modules.customers.infrastructure.models import Customer
from app.modules.customers.schemas.customer import CustomerGetOrCreateByPhone


class GetOrCreateCustomerByPhoneUseCase:
    def __init__(self, customers: CustomerRepository):
        self.customers = customers

    async def execute(self, payload: CustomerGetOrCreateByPhone) -> Customer:
        customer = await self.customers.get_by_phone(payload.phone)
        if customer is not None:
            return customer

        customer = Customer(
            name=payload.name,
            phone=payload.phone,
            email=payload.email,
        )

        await self.customers.add(customer)

        return customer