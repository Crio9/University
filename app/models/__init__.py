from app.db.base import Base
from app.models.dictionaries import Category, Tag
from app.models.post import Post, post_tags
from app.models.profile import StaffProfile, StudentProfile, TeacherProfile
from app.models.raw_content import RawContent, RawContentStatus
from app.models.saved_post import UserSavedPost
from app.models.student_interest import student_interests
from app.models.university import Faculty, StudyGroup, StudyProgram, University
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "StudentProfile",
    "TeacherProfile",
    "StaffProfile",
    "student_interests",
    "University",
    "Faculty",
    "StudyProgram",
    "StudyGroup",
    "Category",
    "Tag",
    "Post",
    "post_tags",
    "RawContent",
    "RawContentStatus",
    "UserSavedPost",
]
