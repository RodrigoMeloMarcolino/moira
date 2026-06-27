import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from app.modules.appointments.application.exceptions import (
    AppointmentBookingConflict,
    AppointmentIdempotencyConflict,
    AppointmentPersistenceConflict,
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
from app.modules.availability.application.public_cache import PublicAvailabilityCache
from app.modules.customers.application.input_ports import CustomerCreatorGetter
from app.modules.customers.schemas.customer import CustomerGetOrCreateByPhone
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.providers.application.exceptions import ProviderNotFound
from app.modules.providers.application.output_ports import ProviderRepository
from app.shared.application.exceptions import (
    UnitOfWorkConflict,
    UnitOfWorkConflictCategory,
)
from app.shared.application.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _BookingContext:
    provider_id: UUID
    offering_id: UUID
    duration_minutes: int
    idempotency_key: str | None
    idempotency_fingerprint: str | None


@dataclass(frozen=True)
class _PreparedBooking(_BookingContext):
    start_at: datetime
    slot_starts: list[datetime]
    end_at: datetime


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
        context = await self._resolve_booking_context(
            provider_slug,
            payload,
            idempotency_key,
        )
        replayed = await self._find_idempotency_replay(context)
        if replayed is not None:
            return replayed

        prepared = await self._prepare_booking(provider_slug, payload, context)
        last_conflict: UnitOfWorkConflict | None = None
        for retry_index in range(2):
            try:
                return await self._persist_booking(payload, prepared)
            except UnitOfWorkConflict as exc:
                last_conflict = exc
                await self.uow.rollback()
                if (
                    exc.category == UnitOfWorkConflictCategory.CUSTOMER_PHONE_UNIQUE
                    and retry_index == 0
                ):
                    self._log_conflict(
                        'customer_phone_created_concurrently',
                        provider_id=prepared.provider_id,
                        offering_id=prepared.offering_id,
                    )
                    continue

                return await self._raise_booking_conflict(exc, prepared)

        raise AppointmentPersistenceConflict(
            'appointment booking failed after retrying customer phone conflict'
        ) from last_conflict

    async def _resolve_booking_context(
        self,
        provider_slug: str,
        payload: PublicAppointmentBookingCreate,
        idempotency_key: str | None,
    ) -> _BookingContext:
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

        provider_id = await self.providers.find_id_by_slug(provider_slug)
        if provider_id is None:
            self._log_rejected('provider_not_found', offering_id=payload.offering_id)
            raise ProviderNotFound(
                f'provider_id not found by slug {provider_slug}',
            )

        if provider_id != offering.provider_id:
            self._log_rejected(
                'offering_mismatch',
                provider_id=provider_id,
                offering_id=offering.id,
            )
            raise OfferingDoesNotBelongToProvider(
                'the requested offering does not belong to this provider',
            )

        return _BookingContext(
            provider_id=provider_id,
            offering_id=offering.id,
            duration_minutes=offering.duration_minutes,
            idempotency_key=idempotency_key,
            idempotency_fingerprint=idempotency_fingerprint,
        )

    async def _prepare_booking(
        self,
        provider_slug: str,
        payload: PublicAppointmentBookingCreate,
        context: _BookingContext,
    ) -> _PreparedBooking:
        requested_start_at = payload.start_at.replace(second=0, microsecond=0)
        try:
            requested_slot_starts = build_occupied_slot_starts(
                requested_start_at,
                context.duration_minutes,
            )
        except StartOutOfBoundary as exc:
            self._log_rejected(
                'invalid_start',
                provider_id=context.provider_id,
                offering_id=context.offering_id,
            )
            raise InvalidAppointmentStart(str(exc)) from exc

        await self._ensure_start_is_available(
            provider_slug,
            context.offering_id,
            context.provider_id,
            requested_start_at,
        )

        start_at = self._normalize_persisted_datetime(requested_start_at)
        slot_starts = [
            self._normalize_persisted_datetime(slot_start_at)
            for slot_start_at in requested_slot_starts
        ]
        return _PreparedBooking(
            provider_id=context.provider_id,
            offering_id=context.offering_id,
            duration_minutes=context.duration_minutes,
            start_at=start_at,
            slot_starts=slot_starts,
            end_at=start_at + timedelta(minutes=context.duration_minutes),
            idempotency_key=context.idempotency_key,
            idempotency_fingerprint=context.idempotency_fingerprint,
        )

    async def _ensure_start_is_available(
        self,
        provider_slug: str,
        offering_id: UUID,
        provider_id: UUID,
        requested_start_at: datetime,
    ) -> None:
        available_starts = await self.list_provider_available_slots.execute(
            provider_slug=provider_slug,
            offering_id=offering_id,
            target_date=requested_start_at.date(),
        )

        if requested_start_at in available_starts:
            return

        self._log_rejected(
            'outside_availability',
            provider_id=provider_id,
            offering_id=offering_id,
        )
        raise AppointmentStartUnavailable(
            'appointment start_at is outside provider availability'
        )

    async def _persist_booking(
        self,
        payload: PublicAppointmentBookingCreate,
        prepared: _PreparedBooking,
    ) -> Appointment:
        customer = await self.get_or_create_customer_by_phone.execute(
            payload=CustomerGetOrCreateByPhone(
                name=payload.customer_name,
                phone=payload.customer_phone,
                email=payload.customer_email,
            )
        )
        await self.uow.flush()

        appointment = Appointment(
            provider_id=prepared.provider_id,
            offering_id=prepared.offering_id,
            customer_id=customer.id,
            start_at=prepared.start_at,
            end_at=prepared.end_at,
            duration_minutes_snapshot=prepared.duration_minutes,
            status='scheduled',
            customer_notes=payload.customer_notes,
            idempotency_key=prepared.idempotency_key,
            idempotency_fingerprint=prepared.idempotency_fingerprint,
        )

        await self.appointments.add(appointment)
        await self.uow.flush()

        appointment_slots = [
            AppointmentSlot(
                appointment_id=appointment.id,
                provider_id=prepared.provider_id,
                slot_start_at=slot_start_at,
            )
            for slot_start_at in prepared.slot_starts
        ]

        await self.appointment_slots.add_many(appointment_slots)
        await self.uow.commit()
        await self.uow.refresh(appointment)
        self._log_succeeded(appointment, prepared)
        await self._invalidate_availability_cache(prepared)

        return appointment

    async def _find_idempotency_replay(
        self,
        prepared: _BookingContext,
    ) -> Appointment | None:
        if prepared.idempotency_key is None:
            return None

        existing_appointment = (
            await self.appointments.get_by_provider_id_and_idempotency_key(
                prepared.provider_id,
                prepared.idempotency_key,
            )
        )
        if existing_appointment is None:
            return None

        self._ensure_idempotency_matches(existing_appointment, prepared)
        self._log_replayed(existing_appointment)
        return existing_appointment

    def _ensure_idempotency_matches(
        self,
        appointment: Appointment,
        prepared: _BookingContext,
    ) -> None:
        if appointment.idempotency_fingerprint == prepared.idempotency_fingerprint:
            return

        self._log_conflict(
            'idempotency_mismatch',
            provider_id=prepared.provider_id,
            offering_id=prepared.offering_id,
            appointment_id=appointment.id,
        )
        raise AppointmentIdempotencyConflict(
            'idempotency key was already used with another payload'
        )

    async def _raise_booking_conflict(
        self,
        exc: UnitOfWorkConflict,
        prepared: _PreparedBooking,
    ) -> Appointment:
        if (
            exc.category
            == UnitOfWorkConflictCategory.APPOINTMENT_IDEMPOTENCY_KEY_UNIQUE
        ):
            replayed = await self._find_idempotency_replay(prepared)
            if replayed is not None:
                return replayed
            self._log_unknown_integrity_conflict(
                'idempotency_replay_missing',
                exc,
                prepared,
            )
            raise AppointmentPersistenceConflict(
                'appointment idempotency conflict could not be replayed'
            ) from exc

        if exc.category == UnitOfWorkConflictCategory.APPOINTMENT_SLOT_UNIQUE:
            self._log_conflict(
                'slot_conflict',
                provider_id=prepared.provider_id,
                offering_id=prepared.offering_id,
            )
            raise AppointmentBookingConflict(
                'appointment time is no longer available'
            ) from exc

        if exc.category == UnitOfWorkConflictCategory.CUSTOMER_PHONE_UNIQUE:
            self._log_unknown_integrity_conflict(
                'customer_phone_retry_exhausted',
                exc,
                prepared,
            )
            raise AppointmentPersistenceConflict(
                'appointment booking failed after customer conflict retry'
            ) from exc

        self._log_unknown_integrity_conflict(
            'unknown_integrity_conflict',
            exc,
            prepared,
        )
        raise AppointmentPersistenceConflict(
            'appointment booking failed due to an integrity conflict'
        ) from exc

    def _log_succeeded(
        self,
        appointment: Appointment,
        prepared: _PreparedBooking,
    ) -> None:
        logger.info(
            'Public appointment booking succeeded',
            extra={
                'event_name': 'appointment.booking_succeeded',
                'appointment.id': appointment.id,
                'provider.id': prepared.provider_id,
                'offering.id': prepared.offering_id,
                'appointment.start_at': prepared.start_at,
                'offering.duration_minutes': prepared.duration_minutes,
                'idempotency.provided': prepared.idempotency_key is not None,
            },
        )

    async def _invalidate_availability_cache(
        self,
        prepared: _PreparedBooking,
    ) -> None:
        if self.public_availability_cache is None:
            return

        try:
            await self.public_availability_cache.invalidate_slots(
                prepared.provider_id,
                prepared.offering_id,
                prepared.start_at.date(),
            )
            await self.public_availability_cache.bump_day_version(
                prepared.provider_id,
                prepared.start_at.date(),
            )
        except Exception as exc:
            logger.warning(
                'Availability cache invalidation failed after booking commit',
                extra={
                    'event_name': 'appointment.cache_invalidation_failed',
                    'reason': type(exc).__name__,
                    'appointment.date': prepared.start_at.date(),
                    'provider.id': prepared.provider_id,
                    'offering.id': prepared.offering_id,
                },
            )

    def _log_unknown_integrity_conflict(
        self,
        reason: str,
        exc: UnitOfWorkConflict,
        prepared: _PreparedBooking,
    ) -> None:
        logger.error(
            'Public appointment booking hit an unhandled integrity conflict',
            extra={
                'event_name': 'appointment.booking_integrity_conflict',
                'reason': reason,
                'uow.reason': exc.reason,
                'uow.category': exc.category,
                'db.constraint_name': exc.constraint_name,
                'provider.id': prepared.provider_id,
                'offering.id': prepared.offering_id,
            },
        )

    def _normalize_persisted_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value

        return value.replace(tzinfo=UTC)

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
