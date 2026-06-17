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
