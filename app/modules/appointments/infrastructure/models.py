from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.base import Base
from app.shared.infrastructure.mixins import TimestampMixin


class Appointment(Base, TimestampMixin):
    __tablename__ = 'appointments'
    __table_args__ = (
        CheckConstraint('start_at < end_at', name='ck_appointments_start_before_end'),
        CheckConstraint(
            'duration_minutes_snapshot > 0',
            name='ck_appointment_duration_snapshot_positive',
        ),
        CheckConstraint(
            'duration_minutes_snapshot % 15 = 0',
            name='ck_appointment_duration_snapshot_multiple_of_15',
        ),
    )

    id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    provider_id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey('providers.id'),
        nullable=False,
    )

    offering_id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey('offerings.id'),
        nullable=False,
    )

    customer_id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True), ForeignKey('customers.id'), nullable=False
    )

    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='scheduled')
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reschedule_token_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )


class AppointmentSlot(Base):
    __tablename__ = 'appointment_slots'
    __table_args__ = (
        UniqueConstraint(
            'provider_id',
            'slot_start_at',
            name='uq_appointment_slots_provider_slot_start',
        ),
    )

    id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    appointment_id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey('appointments.id'),
        nullable=False,
    )

    provider_id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey('providers.id'),
        nullable=False,
    )

    slot_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
