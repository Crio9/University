"""Canonical university hierarchy: University -> Faculty -> Program -> Group."""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class University(Base):
    __tablename__ = "universities"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    faculties: Mapped[list["Faculty"]] = relationship(
        back_populates="university",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Faculty(Base):
    __tablename__ = "faculties"
    __table_args__ = (
        UniqueConstraint("university_id", "name", name="uq_faculties_university_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    university_id: Mapped[int] = mapped_column(
        ForeignKey("universities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    university: Mapped[University] = relationship(back_populates="faculties")
    programs: Mapped[list["StudyProgram"]] = relationship(
        back_populates="faculty",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class StudyProgram(Base):
    __tablename__ = "study_programs"
    __table_args__ = (
        UniqueConstraint("faculty_id", "name", name="uq_study_programs_faculty_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculties.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    faculty: Mapped[Faculty] = relationship(back_populates="programs")
    groups: Mapped[list["StudyGroup"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class StudyGroup(Base):
    __tablename__ = "study_groups"
    __table_args__ = (
        UniqueConstraint(
            "study_program_id", "name", name="uq_study_groups_program_name"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    study_program_id: Mapped[int] = mapped_column(
        ForeignKey("study_programs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    program: Mapped[StudyProgram] = relationship(back_populates="groups")

    @property
    def faculty(self) -> Faculty:
        return self.program.faculty

    @property
    def university(self) -> University:
        return self.program.faculty.university
