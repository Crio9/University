"""Canonical university structure: seeding, resolution and matching helpers.

Invariants enforced here (and mirrored by migrations):

* ``University -> Faculty -> StudyProgram -> StudyGroup`` is the only source of
  truth for a student's university/faculty/program context. A linked
  ``StudentProfile.study_group_id`` determines all three.
* ``course`` stays an explicit ``StudentProfile`` field with the range ``1..6``;
  it is never derived from the group name.
* Changing a student profile never creates canonical entities.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.university import STRUCTURE, UniversitySpec
from app.models.profile import StudentProfile
from app.models.university import Faculty, StudyGroup, StudyProgram, University

COURSE_MIN = 1
COURSE_MAX = 6


def audience_key(value: str) -> str:
    """Normalize a canonical name/alias for comparisons (case and ``ё``)."""
    return " ".join(
        value.strip().casefold().replace("ё", "е").replace("_", " ").split()
    )


async def sync_university_structure(
    db: AsyncSession, structure: tuple[UniversitySpec, ...] = STRUCTURE
) -> None:
    """Insert missing canonical entities. Idempotent; never rewrites existing rows."""
    for university_spec in structure:
        university = await db.scalar(
            select(University).where(University.code == university_spec.code)
        )
        if university is None:
            university = University(
                code=university_spec.code, name=university_spec.name
            )
            db.add(university)
        for faculty_spec in university_spec.faculties:
            faculty = await db.scalar(
                select(Faculty).where(Faculty.code == faculty_spec.code)
            )
            if faculty is None:
                faculty = Faculty(
                    university=university,
                    code=faculty_spec.code,
                    name=faculty_spec.name,
                )
                db.add(faculty)
            for program_spec in faculty_spec.programs:
                program = await db.scalar(
                    select(StudyProgram).where(StudyProgram.code == program_spec.code)
                )
                if program is None:
                    program = StudyProgram(
                        faculty=faculty,
                        code=program_spec.code,
                        name=program_spec.name,
                    )
                    db.add(program)
                for group_spec in program_spec.groups:
                    group = await db.scalar(
                        select(StudyGroup).where(StudyGroup.code == group_spec.code)
                    )
                    if group is None:
                        db.add(
                            StudyGroup(
                                program=program,
                                code=group_spec.code,
                                name=group_spec.name,
                            )
                        )
        await db.flush()


def context_from_group(group: StudyGroup) -> dict:
    """Return canonical labels for known group codes; otherwise use DB labels.

    The historical 0004_university migration seeded some display names which
    differ from current STRUCTURE. Do not rewrite an applied migration here:
    project known codes to one consistent name until a separate data migration.
    """
    program = group.program
    faculty = program.faculty
    university = faculty.university
    for uni_spec in STRUCTURE:
        if uni_spec.code != university.code:
            continue
        for faculty_spec in uni_spec.faculties:
            if faculty_spec.code != faculty.code:
                continue
            for program_spec in faculty_spec.programs:
                if program_spec.code != program.code:
                    continue
                for group_spec in program_spec.groups:
                    if group_spec.code == group.code:
                        return {
                            "university": uni_spec.name,
                            "faculty": faculty_spec.name,
                            "study_program": program_spec.name,
                            "study_group": group_spec.name,
                        }
    return {
        "university": university.name,
        "faculty": faculty.name,
        "study_program": program.name,
        "study_group": group.name,
    }


@dataclass(frozen=True)
class StudentContext:
    """Effective university context used by the feed."""

    university: str | None
    faculty: str | None
    program: str | None
    group: str | None
    course: int | None


def student_context(profile: StudentProfile) -> StudentContext:
    """Resolve the student's context: the canonical group wins over legacy text.

    Legacy text (``university``/``faculty``/``study_program``/``study_group``)
    remains readable for profiles that were not (yet) linked to a canonical
    group, so Sprint 2 targeting keeps working after the migration.
    """
    if profile.study_group_id is not None:
        if profile.group_entity is None:
            raise ValueError("StudentProfile has study_group_id but no loaded StudyGroup")
        derived = context_from_group(profile.group_entity)
        return StudentContext(
            university=derived["university"],
            faculty=derived["faculty"],
            program=derived["study_program"],
            group=derived["study_group"],
            course=profile.course,
        )
    return StudentContext(
        university=profile.university,
        faculty=profile.faculty,
        program=profile.study_program,
        group=profile.study_group,
        course=profile.course,
    )


async def load_profile(db: AsyncSession, user_id: int) -> StudentProfile | None:
    """Load a student profile with its full canonical chain in one query."""
    return await db.scalar(
        select(StudentProfile)
        .where(StudentProfile.user_id == user_id)
        .options(
            selectinload(StudentProfile.group_entity)
            .selectinload(StudyGroup.program)
            .selectinload(StudyProgram.faculty)
            .selectinload(Faculty.university)
        )
    )


async def load_group(db: AsyncSession, group_id: int) -> StudyGroup | None:
    return await db.scalar(
        select(StudyGroup)
        .where(StudyGroup.id == group_id)
        .options(
            selectinload(StudyGroup.program)
            .selectinload(StudyProgram.faculty)
            .selectinload(Faculty.university)
        )
    )


@dataclass(frozen=True)
class CanonicalNames:
    """Canonical names/aliases used to resolve AI audience values."""

    faculties: dict[str, list[str]]
    programs: dict[str, list[str]]
    groups: dict[str, list[str]]


def _remember(
    target: dict[str, list[str]], name: str, aliases: tuple[str, ...], code: str
) -> None:
    key = audience_key(name)
    bucket = target.setdefault(key, [])
    for value in (name, code, *aliases):
        if value and value not in bucket:
            bucket.append(value)


def _remember_db_name(target: dict[str, list[str]], name: str, code: str) -> None:
    """Fold historical DB display names into the STRUCTURE entry by code.

    The migration may say FIST=ФИСТ while STRUCTURE says FIST=ФИТ. Those
    must not become two separate faculty candidates. Do not claim a legacy
    name that another canonical entity already owns (e.g. ИОТ across unis).
    """
    owning_key = next((key for key, values in target.items() if code in values), None)
    if owning_key is None:
        _remember(target, name, (), code)
        return
    normalized_name = audience_key(name)
    conflict = any(
        key != owning_key
        and any(audience_key(alias) == normalized_name for alias in aliases)
        for key, aliases in target.items()
    )
    if not conflict and name not in target[owning_key]:
        target[owning_key].append(name)


async def load_canonical_names(db: AsyncSession) -> CanonicalNames:
    """Collect canonical names plus the aliases declared in ``STRUCTURE``.

    Rows imported outside ``STRUCTURE`` are included as well, so audience
    normalisation stays aligned with what actually exists in the database.
    """
    faculties: dict[str, list[str]] = {}
    programs: dict[str, list[str]] = {}
    groups: dict[str, list[str]] = {}

    for university_spec in STRUCTURE:
        for faculty_spec in university_spec.faculties:
            _remember(
                faculties, faculty_spec.name, faculty_spec.aliases, faculty_spec.code
            )
            for program_spec in faculty_spec.programs:
                _remember(
                    programs, program_spec.name, program_spec.aliases, program_spec.code
                )
                for group_spec in program_spec.groups:
                    _remember(
                        groups, group_spec.name, group_spec.aliases, group_spec.code
                    )

    for row in await db.scalars(select(Faculty)):
        _remember_db_name(faculties, row.name, row.code)
    for row in await db.scalars(select(StudyProgram)):
        _remember_db_name(programs, row.name, row.code)
    for row in await db.scalars(select(StudyGroup)):
        _remember_db_name(groups, row.name, row.code)

    return CanonicalNames(faculties=faculties, programs=programs, groups=groups)


def match_canonical(
    values: list[str], candidates: dict[str, list[str]]
) -> list[str] | None:
    """Map requested audience values to canonical display names.

    Returns ``None`` when at least one requested value is unknown or ambiguous
    (matches several canonical entities). A partially resolved list is never
    returned: dropping a value would silently broaden the audience.
    """
    resolved: list[str] = []
    for value in values:
        key = audience_key(value)
        matches = [
            name
            for name, aliases in candidates.items()
            if key == name or key in {audience_key(alias) for alias in aliases}
        ]
        if len(matches) != 1:
            return None
        display = candidates[matches[0]][0]
        if display not in resolved:
            resolved.append(display)
    return resolved
