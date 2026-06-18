from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot


class AppointmentRepository(Protocol):
    async def add(self, appointment: Appointment) -> None: ...


class AppointmentSlotRepository(Protocol):
    async def add_many(self, appointment_slots: list[AppointmentSlot]) -> None: ...

    async def list_by_provider_and_time_range(
        self,
        provider_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> list[AppointmentSlot]: ...
