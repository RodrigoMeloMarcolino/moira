from datetime import timedelta

from app.modules.appointments.application.exceptions import (
    AppointmentBookingConflict,
    InvalidAppointmentStart,
    OfferingDoesNotBelongToProvider,
)
from app.modules.appointments.application.output_ports import (
    AppointmentRepository,
    AppointmentSlotRepository,
)
from app.modules.appointments.domain.exceptions import StartOutOfBoundary
from app.modules.appointments.domain.slots import build_occupied_slot_starts
from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot
from app.modules.appointments.schemas.booking import PublicAppointmentBookingCreate
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
            uow: UnitOfWork
    ) -> None:
        self.appointments = appointments
        self.offerings = offerings
        self.providers = providers
        self.appointment_slots = appointment_slots
        self.get_or_create_customer_by_phone = get_or_create_customer_by_phone
        self.uow = uow

    async def execute(
            self,
            provider_slug: str,
            payload: PublicAppointmentBookingCreate,
    ) -> Appointment:
        offering = await self.offerings.get_active_by_id(payload.offering_id)
        if offering is None:
            raise OfferingNotFound(
                f"offering not found by offering_id {payload.offering_id}",
            )
        
        provider_id = await self.providers.find_id_by_slug(provider_slug)
        if provider_id is None:
            raise ProviderNotFound(
                f"provider_id not found by slug {provider_slug}",
            )
        
        if provider_id != offering.provider_id:
            raise OfferingDoesNotBelongToProvider(
                "the requested offering does not belong to this provider",
            )
        
        start_at = payload.start_at.replace(second=0, microsecond=0)

        try:
            slots_starts = build_occupied_slot_starts(
                start_at,
                offering.duration_minutes,
            )
        except StartOutOfBoundary as exc:
            raise InvalidAppointmentStart(str(exc)) from exc

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
                status="scheduled",
                customer_notes=payload.customer_notes,
            )

            await self.appointments.add(appointment)
            await self.uow.flush()

            appointment_slots = [
                AppointmentSlot(
                    appointment_id=appointment.id,
                    provider_id=provider_id,
                    slot_start_at=slot_start_at
                )
                for slot_start_at in slots_starts
            ]

            await self.appointment_slots.add_many(appointment_slots)
            await self.uow.commit()
            await self.uow.refresh(appointment)

            return appointment
        except UnitOfWorkConflict as exc:
            await self.uow.rollback()
            raise AppointmentBookingConflict(
                "appointment time is no longer available"
            ) from exc