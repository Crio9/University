"""Input/output contracts for schedule, rescheduling and cancellation."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScheduleState = Literal["NORMAL", "MOVED", "CANCELLED"]


class GroupSelector(BaseModel):
    university: str = Field(min_length=1, max_length=255)
    faculty: str = Field(min_length=1, max_length=255)
    study_program: str = Field(min_length=1, max_length=255)
    study_group: str = Field(min_length=1, max_length=100)


class ScheduleCreate(BaseModel):
    study_group_id: int = Field(gt=0)
    subject: str = Field(min_length=1, max_length=255)
    room: str | None = Field(default=None, max_length=100)
    teacher: str | None = Field(default=None, max_length=255)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def time_order(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Provide starts_at/ends_at with timezone offset")
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must precede ends_at")
        return self


class ScheduleUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    room: str | None = Field(default=None, max_length=100)
    teacher: str | None = Field(default=None, max_length=255)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: ScheduleState | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        for value in (self.starts_at, self.ends_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("Datetime must include a timezone offset")
        return self


class ScheduleRead(GroupSelector):
    model_config = ConfigDict(from_attributes=True)
    study_group_id: int | None
    id: int
    subject: str
    room: str | None
    teacher: str | None
    starts_at: datetime
    ends_at: datetime
    original_starts_at: datetime | None
    original_ends_at: datetime | None
    status: ScheduleState
    created_by: int
    changed_by: int | None


class ScheduleAccessGrant(BaseModel):
    study_group_id: int = Field(gt=0)
    staff_id: int = Field(gt=0)
