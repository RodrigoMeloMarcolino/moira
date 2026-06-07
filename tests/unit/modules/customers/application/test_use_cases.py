from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.customers.application.output_ports import CustomerRepository
from app.modules.customers.application.use_cases import (
    GetOrCreateCustomerByPhoneUseCase,
)
from app.modules.customers.infrastructure.models import Customer
from app.modules.customers.schemas.customer import CustomerGetOrCreateByPhone


def get_or_create_customer_by_phone_payload() -> CustomerGetOrCreateByPhone:
    return CustomerGetOrCreateByPhone(
        name="customer test",
        phone="+5584981175566",
        email="customer@test.com"
    ) 

def customer() -> Customer:
    return Customer(
        id=uuid4(),
        name="customer test",
        phone="+5584981175566",
        email="customer@test.com"
    )

def customer_repository_mock(
        *,
        customer_by_phone: Customer | None = None
) -> Mock:
    customers = Mock(spec=CustomerRepository)
    customers.get_by_phone = AsyncMock(return_value=customer_by_phone)
    customers.add = AsyncMock()

    return customers

def get_or_create_customer_by_phone_use_case(
        *,
        customers: Mock | None = None,
) -> GetOrCreateCustomerByPhoneUseCase:
    return GetOrCreateCustomerByPhoneUseCase(
        customers=customers or customer_repository_mock()
    )

@pytest.mark.asyncio
async def test_get_or_create_customer_by_phone_return_exiting_customer() -> None:
    existing_customer = customer()
    customers = customer_repository_mock(customer_by_phone=existing_customer)
    use_case = get_or_create_customer_by_phone_use_case(
        customers=customers
    )

    result = await use_case.execute(payload=get_or_create_customer_by_phone_payload())

    customers.get_by_phone.assert_awaited_once_with(existing_customer.phone)
    customers.add.assert_not_awaited()

    assert result.name == existing_customer.name
    assert result.phone == existing_customer.phone
    assert result.email == existing_customer.email


@pytest.mark.asyncio
async def test_get_or_create_customer_by_phone_return_new_customer() -> None:
    payload = get_or_create_customer_by_phone_payload()
    customers = customer_repository_mock()
    use_case = get_or_create_customer_by_phone_use_case(
        customers=customers
    )

    result = await use_case.execute(payload=payload)

    customers.get_by_phone.assert_awaited_once_with(payload.phone)
    customers.add.assert_awaited_once()

    added_customer = customers.add.await_args.args[0]

    assert isinstance(added_customer, Customer)
    assert added_customer.name == payload.name
    assert added_customer.phone == payload.phone
    assert added_customer.email == payload.email

    assert result is added_customer