
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AppealCategory(str, Enum):
    ACADEMIC = "ACADEMIC"
    FINANCIAL = "FINANCIAL"
    DORMITORY = "DORMITORY"
    TECHNICAL = "TECHNICAL"


class AppealStatus(str, Enum):
    CREATED = "CREATED"
    IN_REVIEW = "IN_REVIEW"
    CLOSED = "CLOSED"


class AppealCreate(BaseModel):
    category: AppealCategory
    subject: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=10, max_length=10000)


class AppealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    staff_id: int | None
    category: AppealCategory
    subject: str
    message: str
    status: AppealStatus
    staff_response: str | None
    created_at: datetime
    updated_at: datetime


class AppealUpdate(BaseModel):
    status: AppealStatus
    staff_response: str | None = Field(default=None, max_length=10000)
