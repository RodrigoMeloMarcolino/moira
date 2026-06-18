from uuid import UUID

from pydantic import BaseModel, Field


class LoginCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AccessTokenPublic(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    provider_id: UUID
