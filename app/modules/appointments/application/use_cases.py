import logging
from datetime import timedelta
from typing import Optional
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
from app.modules.appointments.domain.timezones import (
    NaiveDateTime,
    provider_local_date,
    resolve_timezone,
    to_utc,
)
from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot
from app.modules.appointments.schemas.booking import PublicAppointmentBookingCreate
from app.modules.availability.application.input_ports import (
    ProviderAvailableSlotsRetriever,
)
from app.modules.availability.application.public_cache import PublicAvailabilityCache
from app.modules.customers.application.input_ports import CustomerCreatorGetter
from app.modules.customers.schemas.customer import CustomerGetOrCreateByPhone
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.providers.application.exceptions import ProviderNotFound
from app.modules.providers.application.output_ports import ProviderRepository
from app.shared.application.exceptions import UnitOfWorkConflict
from app.shared.application.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


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
        public_availability_cache: PublicAvailabilityCache | None = None,
    ) -> None:
        self.appointments = appointments
        self.offerings = offerings
        self.providers = providers
        self.appointment_slots = appointment_slots
        self.get_or_create_customer_by_phone = get_or_create_customer_by_phone
        self.list_provider_available_slots = list_provider_available_slots
        self.uow = uow
        self.public_availability_cache = public_availability_cache

    async def execute(
        self,
        provider_slug: str,
        payload: PublicAppointmentBookingCreate,
        idempotency_key: Optional[str] = None,
    ) -> Appointment:
        idempotency_fingerprint = None
        if idempotency_key is not None:
            idempotency_fingerprint = build_idempotency_fingerprint(
                payload.model_dump(mode='json')
            )

        offering = await self.offerings.get_active_by_id(payload.offering_id)
        if offering is None:
            self._log_rejected('offering_not_found', offering_id=payload.offering_id)
            raise OfferingNotFound(
                f'offering not found by offering_id {payload.offering_id}',
            )

        provider = await self.providers.get_by_slug(provider_slug)
        if provider is None:
            self._log_rejected('provider_not_found', offering_id=payload.offering_id)
            raise ProviderNotFound(
                f'provider_id not found by slug {provider_slug}',
            )
        provider_id = provider.id

        if provider_id != offering.provider_id:
            self._log_rejected(
                'offering_mismatch',
                provider_id=provider_id,
                offering_id=offering.id,
            )
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
                    self._log_conflict(
                        'idempotency_mismatch',
                        provider_id=provider_id,
                        offering_id=offering.id,
                        appointment_id=existing_appointment.id,
                    )
                    raise AppointmentIdempotencyConflict(
                        'idempotency key was already used with another payload'
                    )
                self._log_replayed(existing_appointment)
                return existing_appointment

        try:
            requested_start_at = to_utc(
                payload.start_at.replace(second=0, microsecond=0)
            )
        except NaiveDateTime as exc:
            self._log_rejected(
                'naive_start_at',
                provider_id=provider_id,
                offering_id=offering.id,
            )
            raise InvalidAppointmentStart(str(exc)) from exc

        provider_timezone = resolve_timezone(provider.timezone)
        target_date = provider_local_date(requested_start_at, provider_timezone)

        try:
            requested_slot_starts = build_occupied_slot_starts(
                requested_start_at,
                offering.duration_minutes,
            )
        except StartOutOfBoundary as exc:
            self._log_rejected(
                'invalid_start',
                provider_id=provider_id,
                offering_id=offering.id,
            )
            raise InvalidAppointmentStart(str(exc)) from exc

        available_starts = await self.list_provider_available_slots.execute(
            provider_slug=provider_slug,
            offering_id=payload.offering_id,
            target_date=target_date,
        )

        if requested_start_at not in available_starts:
            self._log_rejected(
                'outside_availability',
                provider_id=provider_id,
                offering_id=offering.id,
            )
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

            start_at = requested_start_at
            slots_starts = requested_slot_starts
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
            logger.info(
                'Public appointment booking succeeded',
                extra={
                    'event_name': 'appointment.booking_succeeded',
                    'appointment.id': appointment.id,
                    'provider.id': provider_id,
                    'offering.id': offering.id,
                    'appointment.start_at': start_at,
                    'offering.duration_minutes': offering.duration_minutes,
                    'idempotency.provided': idempotency_key is not None,
                },
            )
            if self.public_availability_cache is not None:
                await self.public_availability_cache.invalidate_slots(
                    provider_id,
                    offering.id,
                    target_date,
                )
                await self.public_availability_cache.bump_day_version(
                    provider_id,
                    target_date,
                )
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
                        self._log_conflict(
                            'idempotency_mismatch',
                            provider_id=provider_id,
                            offering_id=offering.id,
                            appointment_id=existing_appointment.id,
                        )
                        raise AppointmentIdempotencyConflict(
                            'idempotency key was already used with another payload'
                        ) from exc
                    self._log_replayed(existing_appointment)
                    return existing_appointment

            self._log_conflict(
                'slot_conflict',
                provider_id=provider_id,
                offering_id=payload.offering_id,
            )
            raise AppointmentBookingConflict(
                'appointment time is no longer available'
            ) from exc

    def _log_rejected(
        self,
        reason: str,
        *,
        provider_id: UUID | None = None,
        offering_id: UUID | None = None,
    ) -> None:
        logger.info(
            'Public appointment booking rejected',
            extra={
                'event_name': 'appointment.booking_rejected',
                'reason': reason,
                'provider.id': provider_id,
                'offering.id': offering_id,
            },
        )

    def _log_conflict(
        self,
        reason: str,
        *,
        provider_id: UUID,
        offering_id: UUID,
        appointment_id: UUID | None = None,
    ) -> None:
        logger.warning(
            'Public appointment booking conflicted',
            extra={
                'event_name': 'appointment.booking_conflict',
                'reason': reason,
                'provider.id': provider_id,
                'offering.id': offering_id,
                'appointment.id': appointment_id,
            },
        )

    def _log_replayed(self, appointment: Appointment) -> None:
        logger.info(
            'Public appointment booking replayed',
            extra={
                'event_name': 'appointment.booking_replayed',
                'appointment.id': appointment.id,
                'provider.id': appointment.provider_id,
                'offering.id': appointment.offering_id,
                'idempotency.provided': True,
            },
        )


class ListProviderAppointmentsUseCase:
    def __init__(
        self,
        *,
        appointments: AppointmentRepository,
    ) -> None:
        self.appointments = appointments

    async def execute(self, current_provider_id: UUID) -> list[Appointment]:
        return await self.appointments.list_by_provider_id(current_provider_id)
