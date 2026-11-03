"""Read-only schemas for the canonical university structure."""

from pydantic import BaseModel, ConfigDict


class StudyGroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class StudyProgramRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    groups: list[StudyGroupRead] = []


class FacultyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    programs: list[StudyProgramRead] = []


class UniversityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    faculties: list[FacultyRead] = []
