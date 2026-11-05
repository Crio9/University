from sqlalchemy import JSON, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.university import StudyGroup

from app.db.base import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint(
            "course IS NULL OR (course >= 1 AND course <= 6)",
            name="ck_student_profiles_course_range",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Canonical university context. A profile with a filled-in context must be
    # linked to exactly one StudyGroup; university/faculty/program are then
    # derived from that group (see app/services/university.py).
    study_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # ORM object, distinct from the legacy string field study_group.
    group_entity: Mapped["StudyGroup | None"] = relationship(
        "StudyGroup", foreign_keys=[study_group_id], lazy="selectin"
    )

    # Legacy Sprint 2 text values. Kept so migration never loses the original
    # data; they mirror the linked group whenever a group is selected.
    university: Mapped[str | None] = mapped_column(String(255), nullable=True)
    faculty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    course: Mapped[int | None] = mapped_column(Integer, nullable=True)
    study_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    study_program: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Lossless snapshot of the original (pre-Sprint 3) values for profiles that
    # could not be migrated automatically. Kept so the source data is never lost
    # and can be reported for manual clarification.
    legacy_context: Mapped[dict | None] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"),
        nullable=True,
    )


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    academic_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    office: Mapped[str | None] = mapped_column(String(100), nullable=True)


class StaffProfile(Base):
    __tablename__ = "staff_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
