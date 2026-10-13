from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.post import TagRead


class StudentProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    faculty: str | None = Field(default=None, min_length=1, max_length=255)
    course: int | None = Field(default=None, ge=1, le=6)
    group_name: str | None = None
    interest_tag_ids: list[UUID] | None = None


class StaffProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    department: str | None = None
    position: str | None = None


class StudentProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    faculty: str
    course: int
    group_name: str | None = None
    interests: list[TagRead] = []


class StaffProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    department: str | None = None
    position: str | None = None


class ProfileMeRead(BaseModel):
    user_id: UUID
    email: str
    role: str
    student_profile: StudentProfileRead | None = None
    staff_profile: StaffProfileRead | None = None
