from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.customers.domain.phone import (
    CustomerPhoneInvalid,
    normalize_customer_phone,
)


class PublicAppointmentBookingCreate(BaseModel):
    offering_id: UUID
    start_at: datetime
    customer_name: str = Field(min_length=1, max_length=120)
    customer_phone: str = Field(min_length=8, max_length=32)
    customer_email: str | None = Field(default=None, min_length=3, max_length=255)
    customer_notes: str | None = None

    @field_validator('customer_phone')
    @classmethod
    def validate_customer_phone(cls, value: str) -> str:
        try:
            return normalize_customer_phone(value)
        except CustomerPhoneInvalid as exc:
            raise ValueError(str(exc)) from exc


class AppointmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_id: UUID
    offering_id: UUID
    customer_id: UUID
    start_at: datetime
    end_at: datetime
    duration_minutes_snapshot: int
    status: str
    customer_notes: str | None
