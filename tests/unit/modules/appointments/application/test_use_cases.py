import logging
from datetime import UTC, datetime, timedelta
from typing import Optional
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from app.modules.appointments.application.exceptions import (
    AppointmentIdempotencyConflict,
    AppointmentStartUnavailable,
    InvalidAppointmentStart,
)
from app.modules.appointments.application.output_ports import (
    AppointmentRepository,
    AppointmentSlotRepository,
)
from app.modules.appointments.application.use_cases import (
    BookPublicAppointmentUseCase,
    ListProviderAppointmentsUseCase,
)
from app.modules.appointments.domain.idempotency import build_idempotency_fingerprint
from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot
from app.modules.appointments.schemas.booking import PublicAppointmentBookingCreate
from app.modules.availability.application.input_ports import (
    ProviderAvailableSlotsRetriever,
)
from app.modules.availability.application.public_cache import PublicAvailabilityCache
from app.modules.customers.application.input_ports import CustomerCreatorGetter
from app.modules.customers.infrastructure.models import Customer
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.offerings.infrastructure.models import Offering
from app.modules.providers.application.output_ports import ProviderRepository
from app.modules.providers.infrastructure.models import Provider
from app.shared.application.unit_of_work import UnitOfWork


def offering(provider_id: UUID, *, duration_minutes: int = 30) -> Offering:
    return Offering(
        id=uuid4(),
        provider_id=provider_id,
        title='Consulta',
        description='Atendimento inicial',
        duration_minutes=duration_minutes,
        price_cents=15000,
        is_active=True,
    )


def provider() -> Provider:
    return Provider(
        id=uuid4(),
        user_id=uuid4(),
        display_name='Provider Test',
        slug='provider-test',
        timezone='America/Fortaleza',
        currency_code='BRL',
    )


def customer() -> Customer:
    return Customer(
        id=uuid4(),
        name='Customer Test',
        phone='+155500000000',
        confirmed_phone=True,
        email='customer@example.com',
    )


def appointment(provider_id: UUID, offering_id: UUID) -> Appointment:
    start_at = datetime(2026, 6, 10, 9, 0)
    return Appointment(
        id=uuid4(),
        provider_id=provider_id,
        offering_id=offering_id,
        customer_id=uuid4(),
        start_at=start_at,
        end_at=start_at + timedelta(minutes=30),
        duration_minutes_snapshot=30,
        status='scheduled',
        customer_notes=None,
    )


def booking_payload(
    offering_id: UUID,
    *,
    start_at: datetime,
) -> PublicAppointmentBookingCreate:
    return PublicAppointmentBookingCreate(
        offering_id=offering_id,
        start_at=start_at,
        customer_name='Customer Test',
        customer_phone='+155500000000',
        customer_email='customer@example.com',
        customer_notes='Please call before the appointment.',
    )


def offering_repository_mock(*, active_offering: Optional[Offering] = None) -> Mock:
    offerings = Mock(spec=OfferingRepository)
    offerings.get_active_by_id = AsyncMock(return_value=active_offering)
    return offerings


def provider_repository_mock(
    *,
    provider_id: Optional[UUID] = None,
    provider_by_id: Optional[Provider] = None,
) -> Mock:
    providers = Mock(spec=ProviderRepository)
    providers.find_id_by_slug = AsyncMock(return_value=provider_id)
    providers.get_by_id = AsyncMock(return_value=provider_by_id)
    return providers


def appointment_repository_mock(
    *,
    appointment_by_idempotency_key: Optional[Appointment] = None,
) -> Mock:
    appointments = Mock(spec=AppointmentRepository)
    appointments.add = AsyncMock()
    appointments.get_by_provider_id_and_idempotency_key = AsyncMock(
        return_value=appointment_by_idempotency_key
    )
    appointments.list_by_provider_id = AsyncMock(return_value=[])
    return appointments


def appointment_slot_repository_mock() -> Mock:
    appointment_slots = Mock(spec=AppointmentSlotRepository)
    appointment_slots.add_many = AsyncMock()
    return appointment_slots


def customer_creator_getter_mock(
    *,
    returned_customer: Optional[Customer] = None,
) -> Mock:
    creator_getter = Mock(spec=CustomerCreatorGetter)
    creator_getter.execute = AsyncMock(return_value=returned_customer or customer())
    return creator_getter


def available_slots_retriever_mock(
    *,
    available_starts: list[datetime],
) -> Mock:
    retriever = Mock(spec=ProviderAvailableSlotsRetriever)
    retriever.execute = AsyncMock(return_value=available_starts)
    return retriever


def unit_of_work_mock() -> Mock:
    unit_of_work = Mock(spec=UnitOfWork)
    unit_of_work.flush = AsyncMock()
    unit_of_work.commit = AsyncMock()
    unit_of_work.rollback = AsyncMock()
    unit_of_work.refresh = AsyncMock()
    return unit_of_work


def public_availability_cache_mock() -> Mock:
    cache = Mock(spec=PublicAvailabilityCache)
    cache.invalidate_slots = AsyncMock()
    cache.bump_day_version = AsyncMock(return_value=2)
    return cache


def build_use_case(
    *,
    appointments: Optional[Mock] = None,
    offerings: Optional[Mock] = None,
    providers: Optional[Mock] = None,
    appointment_slots: Optional[Mock] = None,
    get_or_create_customer_by_phone: Optional[Mock] = None,
    list_provider_available_slots: Optional[Mock] = None,
    uow: Optional[Mock] = None,
    public_availability_cache: Optional[Mock] = None,
) -> BookPublicAppointmentUseCase:
    return BookPublicAppointmentUseCase(
        appointments=appointments or appointment_repository_mock(),
        offerings=offerings or offering_repository_mock(),
        providers=providers or provider_repository_mock(),
        appointment_slots=appointment_slots or appointment_slot_repository_mock(),
        get_or_create_customer_by_phone=(
            get_or_create_customer_by_phone or customer_creator_getter_mock()
        ),
        list_provider_available_slots=(
            list_provider_available_slots
            or available_slots_retriever_mock(available_starts=[])
        ),
        uow=uow or unit_of_work_mock(),
        public_availability_cache=public_availability_cache,
    )


@pytest.mark.asyncio
async def test_book_public_appointment_checks_availability_then_books(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    provider_id = uuid4()
    start_at = datetime(2026, 6, 10, 9, 0, 42, 123456)
    expected_requested_start_at = datetime(2026, 6, 10, 9, 0)
    expected_persisted_start_at = datetime(2026, 6, 10, 9, 0, tzinfo=UTC)
    existing_offering = offering(provider_id, duration_minutes=30)
    existing_customer = customer()
    appointments = appointment_repository_mock()
    appointment_slots = appointment_slot_repository_mock()
    customer_creator_getter = customer_creator_getter_mock(
        returned_customer=existing_customer,
    )
    available_slots = available_slots_retriever_mock(
        available_starts=[expected_requested_start_at],
    )
    unit_of_work = unit_of_work_mock()
    public_availability_cache = public_availability_cache_mock()
    use_case = build_use_case(
        appointments=appointments,
        offerings=offering_repository_mock(active_offering=existing_offering),
        providers=provider_repository_mock(provider_id=provider_id),
        appointment_slots=appointment_slots,
        get_or_create_customer_by_phone=customer_creator_getter,
        list_provider_available_slots=available_slots,
        uow=unit_of_work,
        public_availability_cache=public_availability_cache,
    )
    payload = booking_payload(existing_offering.id, start_at=start_at)

    appointment = await use_case.execute('provider-test', payload)

    available_slots.execute.assert_awaited_once_with(
        provider_slug='provider-test',
        offering_id=existing_offering.id,
        target_date=expected_requested_start_at.date(),
    )
    customer_creator_getter.execute.assert_awaited_once()
    appointments.add.assert_awaited_once_with(appointment)
    appointment_slots.add_many.assert_awaited_once()
    unit_of_work.commit.assert_awaited_once_with()
    public_availability_cache.invalidate_slots.assert_awaited_once_with(
        provider_id,
        existing_offering.id,
        expected_requested_start_at.date(),
    )
    public_availability_cache.bump_day_version.assert_awaited_once_with(
        provider_id,
        expected_requested_start_at.date(),
    )
    unit_of_work.refresh.assert_awaited_once_with(appointment)
    assert appointment.provider_id == provider_id
    assert appointment.offering_id == existing_offering.id
    assert appointment.customer_id == existing_customer.id
    assert appointment.start_at == expected_persisted_start_at
    assert appointment.end_at == expected_persisted_start_at + timedelta(minutes=30)
    assert appointment.duration_minutes_snapshot == 30
    assert appointment.status == 'scheduled'
    assert appointment.customer_notes == 'Please call before the appointment.'

    added_slots = appointment_slots.add_many.await_args.args[0]
    assert all(isinstance(slot, AppointmentSlot) for slot in added_slots)
    assert [slot.slot_start_at for slot in added_slots] == [
        expected_persisted_start_at,
        expected_persisted_start_at + timedelta(minutes=15),
    ]
    assert all(slot.provider_id == provider_id for slot in added_slots)
    assert 'appointment.booking_succeeded' in {
        getattr(record, 'event_name', None) for record in caplog.records
    }


@pytest.mark.asyncio
async def test_booking_returns_existing_for_same_idempotency_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    provider_id = uuid4()
    existing_offering = offering(provider_id)
    payload = booking_payload(
        existing_offering.id,
        start_at=datetime(2026, 6, 10, 9, 0),
    )
    existing_appointment = appointment(provider_id, existing_offering.id)
    existing_appointment.idempotency_key = 'retry-key'
    existing_appointment.idempotency_fingerprint = build_idempotency_fingerprint(
        payload.model_dump(mode='json')
    )
    appointments = appointment_repository_mock(
        appointment_by_idempotency_key=existing_appointment,
    )
    available_slots = available_slots_retriever_mock(
        available_starts=[datetime(2026, 6, 10, 9, 0)],
    )
    customer_creator_getter = customer_creator_getter_mock()
    use_case = build_use_case(
        appointments=appointments,
        offerings=offering_repository_mock(active_offering=existing_offering),
        providers=provider_repository_mock(provider_id=provider_id),
        get_or_create_customer_by_phone=customer_creator_getter,
        list_provider_available_slots=available_slots,
    )

    result = await use_case.execute('provider-test', payload, 'retry-key')

    assert result is existing_appointment
    appointments.add.assert_not_awaited()
    available_slots.execute.assert_not_awaited()
    customer_creator_getter.execute.assert_not_awaited()
    assert 'appointment.booking_replayed' in {
        getattr(record, 'event_name', None) for record in caplog.records
    }


@pytest.mark.asyncio
async def test_list_provider_appointments_returns_owned_appointments() -> None:
    existing_provider = provider()
    expected_appointment = appointment(existing_provider.id, uuid4())
    appointments = appointment_repository_mock()
    appointments.list_by_provider_id = AsyncMock(return_value=[expected_appointment])
    use_case = ListProviderAppointmentsUseCase(
        appointments=appointments,
    )

    result = await use_case.execute(existing_provider.id)

    appointments.list_by_provider_id.assert_awaited_once_with(existing_provider.id)
    assert result == [expected_appointment]


@pytest.mark.asyncio
async def test_list_provider_appointments_uses_current_provider_id_from_token() -> None:
    current_provider_id = uuid4()
    appointments = appointment_repository_mock()
    use_case = ListProviderAppointmentsUseCase(
        appointments=appointments,
    )

    await use_case.execute(current_provider_id)

    appointments.list_by_provider_id.assert_awaited_once_with(current_provider_id)


@pytest.mark.asyncio
async def test_book_public_appointment_rejects_reused_idempotency_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider_id = uuid4()
    existing_offering = offering(provider_id)
    existing_appointment = appointment(provider_id, existing_offering.id)
    existing_appointment.idempotency_key = 'retry-key'
    existing_appointment.idempotency_fingerprint = 'another-fingerprint'
    appointments = appointment_repository_mock(
        appointment_by_idempotency_key=existing_appointment,
    )
    use_case = build_use_case(
        appointments=appointments,
        offerings=offering_repository_mock(active_offering=existing_offering),
        providers=provider_repository_mock(provider_id=provider_id),
    )

    with pytest.raises(AppointmentIdempotencyConflict):
        await use_case.execute(
            'provider-test',
            booking_payload(
                existing_offering.id,
                start_at=datetime(2026, 6, 10, 9, 0),
            ),
            'retry-key',
        )

    appointments.add.assert_not_awaited()
    conflict = next(
        record
        for record in caplog.records
        if getattr(record, 'event_name', None) == 'appointment.booking_conflict'
    )
    assert conflict.__dict__['reason'] == 'idempotency_mismatch'


@pytest.mark.asyncio
async def test_book_public_appointment_raises_when_start_is_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    provider_id = uuid4()
    start_at = datetime(2026, 6, 10, 9, 0)
    existing_offering = offering(provider_id)
    appointments = appointment_repository_mock()
    appointment_slots = appointment_slot_repository_mock()
    customer_creator_getter = customer_creator_getter_mock()
    unit_of_work = unit_of_work_mock()
    use_case = build_use_case(
        appointments=appointments,
        offerings=offering_repository_mock(active_offering=existing_offering),
        providers=provider_repository_mock(provider_id=provider_id),
        appointment_slots=appointment_slots,
        get_or_create_customer_by_phone=customer_creator_getter,
        list_provider_available_slots=available_slots_retriever_mock(
            available_starts=[],
        ),
        uow=unit_of_work,
    )

    with pytest.raises(AppointmentStartUnavailable):
        await use_case.execute(
            'provider-test',
            booking_payload(existing_offering.id, start_at=start_at),
        )

    customer_creator_getter.execute.assert_not_awaited()
    appointments.add.assert_not_awaited()
    appointment_slots.add_many.assert_not_awaited()
    unit_of_work.flush.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()
    unit_of_work.refresh.assert_not_awaited()
    rejected = next(
        record
        for record in caplog.records
        if getattr(record, 'event_name', None) == 'appointment.booking_rejected'
    )
    assert rejected.__dict__['reason'] == 'outside_availability'


@pytest.mark.asyncio
async def test_book_public_appointment_rejects_unaligned_start_first() -> None:
    provider_id = uuid4()
    existing_offering = offering(provider_id)
    available_slots = available_slots_retriever_mock(
        available_starts=[datetime(2026, 6, 10, 9, 0)],
    )
    customer_creator_getter = customer_creator_getter_mock()
    use_case = build_use_case(
        offerings=offering_repository_mock(active_offering=existing_offering),
        providers=provider_repository_mock(provider_id=provider_id),
        get_or_create_customer_by_phone=customer_creator_getter,
        list_provider_available_slots=available_slots,
    )

    with pytest.raises(InvalidAppointmentStart):
        await use_case.execute(
            'provider-test',
            booking_payload(
                existing_offering.id,
                start_at=datetime(2026, 6, 10, 9, 10),
            ),
        )

    available_slots.execute.assert_not_awaited()
    customer_creator_getter.execute.assert_not_awaited()
