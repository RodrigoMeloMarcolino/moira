from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_duration(value: int) -> int:
    if value <= 0:
        raise ValueError("duration_minutes must be greater than 0")

    if value % 15 != 0:
        raise ValueError("duration_minutes must be a multiple of 15")

    return value


class OfferingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = None
    duration_minutes: int
    price_cents: int | None = Field(default=None, ge=0)
    is_active: bool = True

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration_minutes(cls, value: int) -> int:
        return validate_duration(value)


class OfferingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    duration_minutes: int | None = None
    price_cents: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("duration_minutes")
    @classmethod
    def validate_duration_minutes(cls, value: int | None) -> int | None:
        if value is None:
            return value

        return validate_duration(value)


class OfferingPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_id: UUID
    title: str
    description: str | None
    duration_minutes: int
    price_cents: int | None
    is_active: bool
