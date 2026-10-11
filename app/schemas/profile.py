from pydantic import BaseModel, Field


class StudentProfileUpdate(BaseModel):
    university: str
    faculty: str
    course: int = Field(ge=1, le=6)
    study_group: str
    study_program: str
    interest_ids: list[int] = Field(default_factory=list)


class TeacherProfileUpdate(BaseModel):
    department: str
    academic_title: str
    office: str


class StaffProfileUpdate(BaseModel):
    department: str
    position: str