from datetime import time
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Time
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.base import Base
from app.shared.infrastructure.mixins import TimestampMixin


class AvailabilityRule(Base, TimestampMixin):
    __tablename__ = 'availability_rules'
    __table_args__ = (
        CheckConstraint(
            'weekday >= 1 AND weekday <= 7',
            name='ck_weekday_valid_range',
        ),
        CheckConstraint(
            'start_time < end_time',
            name='ck_start_before_end',
        ),
        Index(
            'idx_availability_rules_provider_id_weekday',
            'provider_id',
            'weekday',
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

    weekday: Mapped[int] = mapped_column(nullable=False)

    start_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
    )

    end_time: Mapped[time] = mapped_column(
        Time(timezone=False),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default='true',
    )
