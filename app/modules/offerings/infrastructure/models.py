from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.base import Base
from app.shared.infrastructure.mixins import TimestampMixin


class Offering(Base, TimestampMixin):
    __tablename__ = "offerings"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_offerings_duration_positive"),
        CheckConstraint(
            "duration_minutes % 15 = 0", name="ck_offerings_duration_multiple_of_15"
        ),
        CheckConstraint(
            "price_cents IS NULL OR price_cents >= 0",
            name="ck_offerings_price_cents_non_negatives",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    provider_id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey("providers.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
