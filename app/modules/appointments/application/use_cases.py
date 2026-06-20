from datetime import timedelta
from uuid import UUID

from app.modules.appointments.application.exceptions import (
    AppointmentBookingConflict,
    AppointmentIdempotencyConflict,
    AppointmentStartUnavailable,
    InvalidAppointmentStart,
    OfferingDoesNotBelongToProvider,
)
from app.modules.appointments.application.output_ports import (
    AppointmentRepository,
    AppointmentSlotRepository,
)
from app.modules.appointments.domain.exceptions import StartOutOfBoundary
from app.modules.appointments.domain.idempotency import build_idempotency_fingerprint
from app.modules.appointments.domain.slots import build_occupied_slot_starts
from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot
from app.modules.appointments.schemas.booking import PublicAppointmentBookingCreate
from app.modules.availability.application.input_ports import (
    ProviderAvailableSlotsRetriever,
)
from app.modules.customers.application.input_ports import CustomerCreatorGetter
from app.modules.customers.schemas.customer import CustomerGetOrCreateByPhone
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.providers.application.exceptions import ProviderNotFound
from app.modules.providers.application.output_ports import ProviderRepository
from app.shared.application.exceptions import UnitOfWorkConflict
from app.shared.application.unit_of_work import UnitOfWork


class BookPublicAppointmentUseCase:
    def __init__(
        self,
        appointments: AppointmentRepository,
        offerings: OfferingRepository,
        providers: ProviderRepository,
        appointment_slots: AppointmentSlotRepository,
        get_or_create_customer_by_phone: CustomerCreatorGetter,
        list_provider_available_slots: ProviderAvailableSlotsRetriever,
        uow: UnitOfWork,
    ) -> None:
        self.appointments = appointments
        self.offerings = offerings
        self.providers = providers
        self.appointment_slots = appointment_slots
        self.get_or_create_customer_by_phone = get_or_create_customer_by_phone
        self.list_provider_available_slots = list_provider_available_slots
        self.uow = uow

    async def execute(
        self,
        provider_slug: str,
        payload: PublicAppointmentBookingCreate,
        idempotency_key: str | None = None,
    ) -> Appointment:
        idempotency_fingerprint = None
        if idempotency_key is not None:
            idempotency_fingerprint = build_idempotency_fingerprint(
                payload.model_dump(mode='json')
            )

        offering = await self.offerings.get_active_by_id(payload.offering_id)
        if offering is None:
            raise OfferingNotFound(
                f'offering not found by offering_id {payload.offering_id}',
            )

        provider_id = await self.providers.find_id_by_slug(provider_slug)
        if provider_id is None:
            raise ProviderNotFound(
                f'provider_id not found by slug {provider_slug}',
            )

        if provider_id != offering.provider_id:
            raise OfferingDoesNotBelongToProvider(
                'the requested offering does not belong to this provider',
            )

        if idempotency_key is not None:
            existing_appointment = (
                await self.appointments.get_by_provider_id_and_idempotency_key(
                    provider_id,
                    idempotency_key,
                )
            )
            if existing_appointment is not None:
                if (
                    existing_appointment.idempotency_fingerprint
                    != idempotency_fingerprint
                ):
                    raise AppointmentIdempotencyConflict(
                        'idempotency key was already used with another payload'
                    )

                return existing_appointment

        start_at = payload.start_at.replace(second=0, microsecond=0)

        try:
            slots_starts = build_occupied_slot_starts(
                start_at,
                offering.duration_minutes,
            )
        except StartOutOfBoundary as exc:
            raise InvalidAppointmentStart(str(exc)) from exc

        available_starts = await self.list_provider_available_slots.execute(
            provider_slug=provider_slug,
            offering_id=payload.offering_id,
            target_date=start_at.date(),
        )

        if start_at not in available_starts:
            raise AppointmentStartUnavailable(
                'appointment start_at is outside provider availability'
            )

        try:
            customer = await self.get_or_create_customer_by_phone.execute(
                payload=CustomerGetOrCreateByPhone(
                    name=payload.customer_name,
                    phone=payload.customer_phone,
                    email=payload.customer_email,
                )
            )
            await self.uow.flush()

            end_at = start_at + timedelta(minutes=offering.duration_minutes)

            appointment = Appointment(
                provider_id=provider_id,
                offering_id=offering.id,
                customer_id=customer.id,
                start_at=start_at,
                end_at=end_at,
                duration_minutes_snapshot=offering.duration_minutes,
                status='scheduled',
                customer_notes=payload.customer_notes,
                idempotency_key=idempotency_key,
                idempotency_fingerprint=idempotency_fingerprint,
            )

            await self.appointments.add(appointment)
            await self.uow.flush()

            appointment_slots = [
                AppointmentSlot(
                    appointment_id=appointment.id,
                    provider_id=provider_id,
                    slot_start_at=slot_start_at,
                )
                for slot_start_at in slots_starts
            ]

            await self.appointment_slots.add_many(appointment_slots)
            await self.uow.commit()
            await self.uow.refresh(appointment)

            return appointment
        except UnitOfWorkConflict as exc:
            await self.uow.rollback()
            if idempotency_key is not None:
                existing_appointment = (
                    await self.appointments.get_by_provider_id_and_idempotency_key(
                        provider_id,
                        idempotency_key,
                    )
                )
                if existing_appointment is not None:
                    if (
                        existing_appointment.idempotency_fingerprint
                        != idempotency_fingerprint
                    ):
                        raise AppointmentIdempotencyConflict(
                            'idempotency key was already used with another payload'
                        ) from exc

                    return existing_appointment

            raise AppointmentBookingConflict(
                'appointment time is no longer available'
            ) from exc


class ListProviderAppointmentsUseCase:
    def __init__(
        self,
        *,
        appointments: AppointmentRepository,
    ) -> None:
        self.appointments = appointments

    async def execute(self, current_provider_id: UUID) -> list[Appointment]:
        return await self.appointments.list_by_provider_id(current_provider_id)
