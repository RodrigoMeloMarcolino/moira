from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.auth.domain.password_policy import (
    MAX_SIGNUP_PASSWORD_LENGTH,
    MIN_SIGNUP_PASSWORD_LENGTH,
)


class ProviderSignupCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(
        min_length=MIN_SIGNUP_PASSWORD_LENGTH,
        max_length=MAX_SIGNUP_PASSWORD_LENGTH,
    )
    display_name: str = Field(min_length=1, max_length=120)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    currency_code: str = Field(default='BRL', min_length=3, max_length=3)

    @field_validator('display_name')
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            msg = 'display_name must not be empty'
            raise ValueError(msg)

        return normalized

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError('timezone must be a valid IANA timezone') from exc

        return value


class ProviderPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: str
    slug: str
    timezone: str
    currency_code: str


class ProviderCatalogPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    slug: str
    timezone: str
    currency_code: str
