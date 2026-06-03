from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.domain.password_policy import (
    MAX_SIGNUP_PASSWORD_LENGTH,
    MIN_SIGNUP_PASSWORD_LENGTH,
)


class ProviderSignupCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(
        min_length=MIN_SIGNUP_PASSWORD_LENGTH,
        max_length=MAX_SIGNUP_PASSWORD_LENGTH,
    )
    display_name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)
    timezone: str = Field(default="America/Fortaleza", min_length=1, max_length=64)
    currency_code: str = Field(default="BRL", min_length=3, max_length=3)


class ProviderPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: str
    slug: str
    timezone: str
    currency_code: str
