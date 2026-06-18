from uuid import UUID, uuid4

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.base import Base
from app.shared.infrastructure.mixins import TimestampMixin


class Customer(Base, TimestampMixin):
    __tablename__ = 'customers'
    __table_args__ = (UniqueConstraint('phone', name='uq_customers_phone'),)

    id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    #   Temporary field, on the final version of customer activation, it will be
    #   replaced by phone_confirmed_at: timestamp
    confirmed_phone: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
