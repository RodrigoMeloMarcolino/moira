from pydantic import BaseModel, Field, field_validator

from app.modules.customers.domain.phone import (
    CustomerPhoneInvalid,
    normalize_customer_phone,
)


class CustomerGetOrCreateByPhone(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=8, max_length=32)
    email: str | None = Field(default=None, min_length=3, max_length=255)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str) -> str:
        try:
            return normalize_customer_phone(value)
        except CustomerPhoneInvalid as exc:
            raise ValueError(str(exc)) from exc
