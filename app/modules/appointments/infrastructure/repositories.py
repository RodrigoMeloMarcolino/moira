from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot


class SQLAlchemyAppointmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, appointment: Appointment) -> None:
        self.session.add(appointment)

    async def get_by_provider_id_and_idempotency_key(
        self,
        provider_id: UUID,
        idempotency_key: str,
    ) -> Appointment | None:
        return await self.session.scalar(
            select(Appointment).where(
                Appointment.provider_id == provider_id,
                Appointment.idempotency_key == idempotency_key,
            )
        )

    async def list_by_provider_id(self, provider_id: UUID) -> list[Appointment]:
        result = await self.session.scalars(
            select(Appointment)
            .where(Appointment.provider_id == provider_id)
            .order_by(Appointment.start_at)
        )

        return list(result)


class SQLAlchemyAppointmentSlotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(self, appointment_slots: list[AppointmentSlot]) -> None:
        self.session.add_all(appointment_slots)

    async def list_by_provider_and_time_range(
        self,
        provider_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> list[AppointmentSlot]:
        result = await self.session.scalars(
            select(AppointmentSlot)
            .where(
                AppointmentSlot.provider_id == provider_id,
                AppointmentSlot.slot_start_at >= start_at,
                AppointmentSlot.slot_start_at < end_at,
            )
            .order_by(AppointmentSlot.slot_start_at)
        )

        return list(result)
