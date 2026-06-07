from typing import Protocol

from app.modules.appointments.infrastructure.models import Appointment, AppointmentSlot


class AppointmentRepository(Protocol):
    async def add(self, appointment: Appointment) -> None: ...


class AppointmentSlotRepository(Protocol):
    async def add_many(self, appointment_slots: list[AppointmentSlot]) -> None: ...
