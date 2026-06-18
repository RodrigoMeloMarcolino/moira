import asyncio
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.appointments.application.exceptions import (
    AppointmentBookingConflict,
    AppointmentStartUnavailable,
    InvalidAppointmentStart,
    OfferingDoesNotBelongToProvider,
)
from app.modules.appointments.application.use_cases import (
    BookPublicAppointmentUseCase,
)
from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot
from app.modules.appointments.infrastructure.repositories import (
    SQLAlchemyAppointmentRepository,
    SQLAlchemyAppointmentSlotRepository,
)
from app.modules.appointments.schemas.booking import PublicAppointmentBookingCreate
from app.modules.customers.application.use_cases import (
    GetOrCreateCustomerByPhoneUseCase,
)
from app.modules.customers.infrastructure.models import Customer
from app.modules.customers.infrastructure.repositories import (
    SQLAlchemyCustomerRepository,
)
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.infrastructure.models import Offering
from app.modules.offerings.infrastructure.repositories import (
    SqlAlchemyOfferingRepository,
)
from app.modules.providers.application.exceptions import ProviderNotFound
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.infrastructure.repositories import (
    SqlAlchemyProviderRepository,
)
from app.modules.users.infrastructure.models import User
from app.shared.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def async_session_factory():
    from app.database import async_session_factory as factory

    return factory()


def unique_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def unique_phone() -> str:
    return f"+1555{uuid4().int % 10_000_000_000:010d}"


class AvailableSlotsRetrieverStub:
    def __init__(self, available_starts: list[datetime] | None = None) -> None:
        self.available_starts = available_starts
        self.calls: list[tuple[str, UUID, object]] = []

    async def execute(
        self,
        provider_slug: str,
        offering_id: UUID,
        target_date: date,
    ) -> list[datetime]:
        self.calls.append((provider_slug, offering_id, target_date))

        if self.available_starts is not None:
            return self.available_starts

        day_start = datetime.combine(target_date, time.min, tzinfo=UTC)
        return [
            day_start + timedelta(minutes=offset) for offset in range(0, 24 * 60, 15)
        ]


def build_use_case(
    session: AsyncSession,
    *,
    available_slots: AvailableSlotsRetrieverStub | None = None,
) -> BookPublicAppointmentUseCase:
    available_slots_retriever = available_slots or AvailableSlotsRetrieverStub()
    get_or_create_customer_by_phone = GetOrCreateCustomerByPhoneUseCase(
        customers=SQLAlchemyCustomerRepository(session),
    )

    return BookPublicAppointmentUseCase(
        appointments=SQLAlchemyAppointmentRepository(session),
        appointment_slots=SQLAlchemyAppointmentSlotRepository(session),
        offerings=SqlAlchemyOfferingRepository(session),
        providers=SqlAlchemyProviderRepository(session),
        get_or_create_customer_by_phone=get_or_create_customer_by_phone,
        list_provider_available_slots=available_slots_retriever,
        uow=SqlAlchemyUnitOfWork(session),
    )


def booking_payload(
    offering_id: UUID,
    *,
    start_at: datetime,
    customer_phone: str,
    customer_name: str = "Customer Test",
    customer_email: str | None = "customer@example.com",
    customer_notes: str | None = "Please call before the appointment.",
) -> PublicAppointmentBookingCreate:
    return PublicAppointmentBookingCreate(
        offering_id=offering_id,
        start_at=start_at,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_email=customer_email,
        customer_notes=customer_notes,
    )


async def create_provider_with_offering(
    session: AsyncSession,
    *,
    duration_minutes: int = 30,
    is_active: bool = True,
) -> tuple[Provider, Offering]:
    marker = uuid4().hex
    user = User(
        id=uuid4(),
        email=f"{marker}@example.com",
        password_hash="hashed-password",
    )
    provider = Provider(
        id=uuid4(),
        user_id=user.id,
        display_name="Provider Test",
        slug=unique_value("provider"),
        timezone="America/Fortaleza",
        currency_code="BRL",
    )
    offering = Offering(
        id=uuid4(),
        provider_id=provider.id,
        title="Consulta",
        description="Atendimento inicial",
        duration_minutes=duration_minutes,
        price_cents=15000,
        is_active=is_active,
    )

    session.add(user)
    await session.flush()

    session.add(provider)
    await session.flush()

    session.add(offering)
    await session.commit()

    return provider, offering


async def create_customer(
    session: AsyncSession,
    *,
    phone: str,
    name: str = "Existing Customer",
    email: str | None = "existing@example.com",
) -> Customer:
    customer = Customer(
        id=uuid4(),
        name=name,
        phone=phone,
        confirmed_phone=True,
        email=email,
    )

    session.add(customer)
    await session.commit()

    return customer


async def count_customers_by_phone(session: AsyncSession, phone: str) -> int:
    count = await session.scalar(
        select(func.count()).select_from(Customer).where(Customer.phone == phone)
    )
    return int(count or 0)


async def get_customer_by_phone(session: AsyncSession, phone: str) -> Customer | None:
    return await session.scalar(select(Customer).where(Customer.phone == phone))


async def count_appointments_by_offering(
    session: AsyncSession,
    offering_id: UUID,
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Appointment)
        .where(Appointment.offering_id == offering_id)
    )
    return int(count or 0)


async def list_provider_appointments(
    session: AsyncSession,
    provider_id: UUID,
) -> list[Appointment]:
    result = await session.scalars(
        select(Appointment)
        .where(Appointment.provider_id == provider_id)
        .order_by(Appointment.start_at)
    )
    return list(result)


async def list_appointment_slots(
    session: AsyncSession,
    appointment_id: UUID,
) -> list[AppointmentSlot]:
    result = await session.scalars(
        select(AppointmentSlot)
        .where(AppointmentSlot.appointment_id == appointment_id)
        .order_by(AppointmentSlot.slot_start_at)
    )
    return list(result)


async def execute_booking(
    provider_slug: str,
    payload: PublicAppointmentBookingCreate,
) -> Appointment:
    async with async_session_factory() as session:
        return await build_use_case(session).execute(provider_slug, payload)


async def test_books_public_appointment_for_new_customer() -> None:
    raw_start_at = datetime(2026, 6, 10, 9, 0, 42, 123456, tzinfo=UTC)
    expected_start_at = datetime(2026, 6, 10, 9, 0, tzinfo=UTC)
    customer_phone = unique_phone()

    async with async_session_factory() as session:
        provider, offering = await create_provider_with_offering(session)
        payload = booking_payload(
            offering.id,
            start_at=raw_start_at,
            customer_phone=customer_phone,
        )

        appointment = await build_use_case(session).execute(provider.slug, payload)

    assert appointment.provider_id == provider.id
    assert appointment.offering_id == offering.id
    assert appointment.start_at == expected_start_at
    assert appointment.end_at == expected_start_at + timedelta(minutes=30)
    assert appointment.duration_minutes_snapshot == 30
    assert appointment.status == "scheduled"
    assert appointment.customer_notes == "Please call before the appointment."

    async with async_session_factory() as session:
        customer = await get_customer_by_phone(session, customer_phone)
        db_appointment = await session.get(Appointment, appointment.id)
        slots = await list_appointment_slots(session, appointment.id)

    assert customer is not None
    assert customer.name == "Customer Test"
    assert customer.email == "customer@example.com"
    assert db_appointment is not None
    assert db_appointment.customer_id == customer.id
    assert db_appointment.start_at == expected_start_at
    assert db_appointment.end_at == expected_start_at + timedelta(minutes=30)
    assert [slot.slot_start_at for slot in slots] == [
        expected_start_at,
        expected_start_at + timedelta(minutes=15),
    ]
    assert all(slot.provider_id == provider.id for slot in slots)


async def test_books_public_appointment_reusing_existing_customer() -> None:
    start_at = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
    customer_phone = unique_phone()

    async with async_session_factory() as session:
        provider, offering = await create_provider_with_offering(session)
        existing_customer = await create_customer(session, phone=customer_phone)
        payload = booking_payload(
            offering.id,
            start_at=start_at,
            customer_phone=customer_phone,
            customer_name="New Submitted Name",
            customer_email="new@example.com",
        )

        appointment = await build_use_case(session).execute(provider.slug, payload)

    assert appointment.customer_id == existing_customer.id

    async with async_session_factory() as session:
        customer_count = await count_customers_by_phone(session, customer_phone)
        customer = await get_customer_by_phone(session, customer_phone)
        db_appointment = await session.get(Appointment, appointment.id)

    assert customer_count == 1
    assert customer is not None
    assert customer.id == existing_customer.id
    assert db_appointment is not None
    assert db_appointment.customer_id == existing_customer.id


async def test_book_public_appointment_raises_when_offering_is_missing() -> None:
    customer_phone = unique_phone()
    missing_offering_id = uuid4()
    payload = booking_payload(
        missing_offering_id,
        start_at=datetime(2026, 6, 10, 11, 0, tzinfo=UTC),
        customer_phone=customer_phone,
    )

    async with async_session_factory() as session:
        with pytest.raises(OfferingNotFound):
            await build_use_case(session).execute("missing-provider", payload)

    async with async_session_factory() as session:
        assert await count_customers_by_phone(session, customer_phone) == 0
        assert await count_appointments_by_offering(session, missing_offering_id) == 0


async def test_book_public_appointment_raises_when_offering_is_inactive() -> None:
    customer_phone = unique_phone()

    async with async_session_factory() as session:
        provider, offering = await create_provider_with_offering(
            session,
            is_active=False,
        )
        payload = booking_payload(
            offering.id,
            start_at=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
            customer_phone=customer_phone,
        )

        with pytest.raises(OfferingNotFound):
            await build_use_case(session).execute(provider.slug, payload)

    async with async_session_factory() as session:
        assert await count_customers_by_phone(session, customer_phone) == 0
        assert await count_appointments_by_offering(session, offering.id) == 0


async def test_book_public_appointment_raises_when_provider_is_missing() -> None:
    customer_phone = unique_phone()

    async with async_session_factory() as session:
        _, offering = await create_provider_with_offering(session)
        payload = booking_payload(
            offering.id,
            start_at=datetime(2026, 6, 10, 13, 0, tzinfo=UTC),
            customer_phone=customer_phone,
        )

        with pytest.raises(ProviderNotFound):
            await build_use_case(session).execute("missing-provider", payload)

    async with async_session_factory() as session:
        assert await count_customers_by_phone(session, customer_phone) == 0
        assert await count_appointments_by_offering(session, offering.id) == 0


async def test_book_public_appointment_raises_for_other_provider_offering() -> None:
    customer_phone = unique_phone()

    async with async_session_factory() as session:
        _, offering = await create_provider_with_offering(session)
        other_provider, _ = await create_provider_with_offering(session)
        payload = booking_payload(
            offering.id,
            start_at=datetime(2026, 6, 10, 14, 0, tzinfo=UTC),
            customer_phone=customer_phone,
        )

        with pytest.raises(OfferingDoesNotBelongToProvider):
            await build_use_case(session).execute(other_provider.slug, payload)

    async with async_session_factory() as session:
        assert await count_customers_by_phone(session, customer_phone) == 0
        assert await count_appointments_by_offering(session, offering.id) == 0


async def test_book_public_appointment_raises_when_start_is_out_of_boundary() -> None:
    customer_phone = unique_phone()

    async with async_session_factory() as session:
        provider, offering = await create_provider_with_offering(session)
        payload = booking_payload(
            offering.id,
            start_at=datetime(2026, 6, 10, 15, 10, tzinfo=UTC),
            customer_phone=customer_phone,
        )

        with pytest.raises(InvalidAppointmentStart):
            await build_use_case(session).execute(provider.slug, payload)

    async with async_session_factory() as session:
        assert await count_customers_by_phone(session, customer_phone) == 0
        assert await count_appointments_by_offering(session, offering.id) == 0


async def test_book_public_appointment_raises_when_start_is_unavailable() -> None:
    customer_phone = unique_phone()
    start_at = datetime(2026, 6, 10, 15, 0, tzinfo=UTC)
    available_slots = AvailableSlotsRetrieverStub(available_starts=[])

    async with async_session_factory() as session:
        provider, offering = await create_provider_with_offering(session)
        payload = booking_payload(
            offering.id,
            start_at=start_at,
            customer_phone=customer_phone,
        )

        with pytest.raises(AppointmentStartUnavailable):
            await build_use_case(
                session,
                available_slots=available_slots,
            ).execute(provider.slug, payload)

    assert available_slots.calls == [(provider.slug, offering.id, start_at.date())]

    async with async_session_factory() as session:
        assert await count_customers_by_phone(session, customer_phone) == 0
        assert await count_appointments_by_offering(session, offering.id) == 0


async def test_book_public_appointment_raises_on_partially_overlapping_slot() -> None:
    first_phone = unique_phone()
    second_phone = unique_phone()
    first_start_at = datetime(2026, 6, 10, 16, 0, tzinfo=UTC)
    second_start_at = first_start_at + timedelta(minutes=15)

    async with async_session_factory() as session:
        provider, offering = await create_provider_with_offering(session)
        first_payload = booking_payload(
            offering.id,
            start_at=first_start_at,
            customer_phone=first_phone,
        )
        second_payload = booking_payload(
            offering.id,
            start_at=second_start_at,
            customer_phone=second_phone,
        )
        first_appointment = await build_use_case(session).execute(
            provider.slug,
            first_payload,
        )
        provider_id = provider.id
        first_appointment_id = first_appointment.id

        with pytest.raises(AppointmentBookingConflict):
            await build_use_case(session).execute(provider.slug, second_payload)

    async with async_session_factory() as session:
        appointments = await list_provider_appointments(session, provider_id)
        slots = await list_appointment_slots(session, first_appointment_id)

        assert await count_customers_by_phone(session, first_phone) == 1
        assert await count_customers_by_phone(session, second_phone) == 0

    assert [appointment.id for appointment in appointments] == [first_appointment_id]
    assert [slot.slot_start_at for slot in slots] == [
        first_start_at,
        first_start_at + timedelta(minutes=15),
    ]


async def test_book_public_appointment_allows_one_concurrent_slot_booking() -> None:
    start_at = datetime(2026, 6, 10, 17, 0, tzinfo=UTC)

    async with async_session_factory() as session:
        provider, offering = await create_provider_with_offering(session)

    first_payload = booking_payload(
        offering.id,
        start_at=start_at,
        customer_phone=unique_phone(),
    )
    second_payload = booking_payload(
        offering.id,
        start_at=start_at,
        customer_phone=unique_phone(),
    )

    results = await asyncio.gather(
        execute_booking(provider.slug, first_payload),
        execute_booking(provider.slug, second_payload),
        return_exceptions=True,
    )

    successful_bookings = [
        result for result in results if isinstance(result, Appointment)
    ]
    booking_conflicts = [
        result for result in results if isinstance(result, AppointmentBookingConflict)
    ]

    assert len(successful_bookings) == 1
    assert len(booking_conflicts) == 1

    async with async_session_factory() as session:
        appointments = await list_provider_appointments(session, provider.id)
        slots = await list_appointment_slots(session, successful_bookings[0].id)

    assert [appointment.id for appointment in appointments] == [
        successful_bookings[0].id
    ]
    assert [slot.slot_start_at for slot in slots] == [
        start_at,
        start_at + timedelta(minutes=15),
    ]
