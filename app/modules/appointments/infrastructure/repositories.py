
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