from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as pgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.infrastructure.base import Base
from app.shared.infrastructure.mixins import TimestampMixin


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        pgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    display_name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="America/Fortaleza"
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="BRL",
        server_default="BRL",
    )
