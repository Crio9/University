from pydantic import BaseModel, Field, model_validator


from app.schemas.opportunity import OpportunityType


class StudentProfileUpdate(BaseModel):
    # Sprint 3 canonical context: an existing StudyGroup is required for a
    # filled-in profile. University/faculty/program are derived from it.
    faculty_id: int | None = Field(default=None, gt=0)
    study_program_id: int | None = Field(default=None, gt=0)
    preferred_types: list[OpportunityType] = Field(default_factory=list)
    study_group_id: int | None = Field(default=None, gt=0)
    course: int | None = Field(default=None, ge=1, le=6)
    # Legacy text fields stay optional/read-only for Sprint 2 clients; a group
    # selection always overwrites them with the canonical chain.
    university: str = Field(default="", max_length=255)
    faculty: str = Field(default="", max_length=255)
    study_group: str = Field(default="", max_length=100)
    study_program: str = Field(default="", max_length=255)
    interest_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_group_for_filled_profile(self):
        if (self.faculty_id is None) != (self.study_program_id is None):
            raise ValueError("Select both faculty and program")
        if self.study_program_id and (self.study_group_id or not self.interest_ids):
            raise ValueError("Select interests and use a program without a group")
        has_text = any(
            value.strip() for value in (self.university, self.faculty, self.study_group, self.study_program)
        )
        if has_text and self.study_group_id is None:
            raise ValueError("study_group_id is required for a filled-in profile")
        return self


class TeacherProfileUpdate(BaseModel):
    department: str = ""
    academic_title: str = ""
    office: str = ""


class StaffProfileUpdate(BaseModel):
    department: str = ""
    position: str = ""
