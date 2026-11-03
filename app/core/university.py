"""Canonical university structure used by seed/import and migration mapping.

This module is the single source of truth for the demonstration hierarchy
``University -> Faculty -> StudyProgram -> StudyGroup``. Names are unique per
parent (faculties inside a university, programs inside a faculty, groups inside
a program), so the same label may legitimately exist under different parents.

``STRUCTURE`` is seeded in a deterministic order: universities first, then
faculties, programs and groups, each referencing its parent by code.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GroupSpec:
    code: str
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProgramSpec:
    code: str
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    groups: tuple[GroupSpec, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FacultySpec:
    code: str
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    programs: tuple[ProgramSpec, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class UniversitySpec:
    code: str
    name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    faculties: tuple[FacultySpec, ...] = field(default_factory=tuple)


STRUCTURE: tuple[UniversitySpec, ...] = (
    UniversitySpec(
        code="DSTU",
        name="Донской государственный технический университет",
        aliases=("ДГТУ", "DSTU"),
        faculties=(
            FacultySpec(
                code="FIST",
                name="ФИТ",
                aliases=("ФИСТ", "Факультет информационных систем и технологий"),
                programs=(
                    ProgramSpec(
                        code="PMI",
                        name="ПМИ",
                        aliases=("Прикладная математика и информатика",),
                        groups=(
                            GroupSpec("IVT-21", "ИВТ-21"),
                            GroupSpec("IVT-31", "ИВТ-31"),
                            GroupSpec("IVT-41", "ИВТ-41"),
                        ),
                    ),
                    ProgramSpec(
                        code="IS",
                        name="ИС",
                        aliases=("Информационные системы",),
                        groups=(
                            GroupSpec("FIST-31", "ФИСТ-31"),
                            GroupSpec("FIST-21", "ФИСТ-21"),
                        ),
                    ),
                ),
            ),
            FacultySpec(
                code="IOT",
                name="ИОТ",
                aliases=("Институт опережающих технологий",),
                programs=(
                    ProgramSpec(
                        code="PMI-IOT",
                        name="ПМИ ИОТ",
                        aliases=("Прикладная математика и информатика (ИОТ)",),
                        groups=(
                            GroupSpec("IOT-31", "ИОТ-31"),
                            GroupSpec("IOT-41", "ИОТ-41"),
                        ),
                    ),
                ),
            ),
            FacultySpec(
                code="LAW",
                name="Юрфак",
                aliases=("Юридический факультет",),
                programs=(
                    ProgramSpec(
                        code="LAW-PR",
                        name="Право",
                        aliases=("Юриспруденция",),
                        groups=(GroupSpec("UR-31", "ЮР-31"),),
                    ),
                ),
            ),
        ),
    ),
    UniversitySpec(
        code="SFEDU",
        name="Южный федеральный университет",
        aliases=("ЮФУ",),
        faculties=(
            FacultySpec(
                code="SFEDU-IOT",
                name="ИОТ ЮФУ",
                aliases=("Институт опережающих технологий ЮФУ",),
                programs=(
                    ProgramSpec(
                        code="SFEDU-IOT-PMI",
                        name="ПМИ ЮФУ",
                        aliases=("Прикладная математика и информатика (ЮФУ)",),
                        groups=(GroupSpec("SFEDU-IVT-31", "ЮФУ-ИВТ-31"),),
                    ),
                ),
            ),
        ),
    ),
)
