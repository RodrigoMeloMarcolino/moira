from datetime import date, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AvailabilityRuleCreate(BaseModel):
    weekday: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    is_active: Optional[bool] = Field(default=True)

    @field_validator('start_time', 'end_time')
    @classmethod
    def must_only_have_hour_and_minute(cls, value: time) -> time:
        if value.second != 0 or value.microsecond != 0:
            raise ValueError('time must contain only hour and minute')
        return value


class AvailabilityRuleUpdate(BaseModel):
    weekday: Optional[int] = Field(default=None, ge=1, le=7)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None

    @field_validator('start_time', 'end_time')
    @classmethod
    def must_only_have_hour_and_minute(cls, value: Optional[time]) -> Optional[time]:
        if value is None:
            return value
        if value.second != 0 or value.microsecond != 0:
            raise ValueError('time must contain only hour and minute')
        return value


class AvailabilityRulePublicQuery(BaseModel):
    offering_id: UUID
    date: date


class AvailabilityRulePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_id: UUID
    weekday: int
    start_time: time
    end_time: time
    is_active: bool
