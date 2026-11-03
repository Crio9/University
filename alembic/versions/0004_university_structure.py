"""Canonical university structure and StudentProfile migration.

Revision ID: 0004_university
Revises: 0003_ai_audience

Adds the canonical hierarchy ``University -> Faculty -> StudyProgram ->
StudyGroup`` (FR-1.*), links :class:`StudentProfile` to a single group, and
migrates existing text values:

  * unambiguous legacy rows are linked to the matching group automatically;
  * empty / ambiguous / unknown rows are left untouched (no fake entities) and
    their original values are preserved in ``student_profiles.legacy_context``;
  * ``course`` is constrained to ``1..6``; out-of-range values are preserved in
    ``legacy_context`` and set to ``NULL`` instead of being invented.
"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_university"
down_revision: Union[str, None] = "0003_ai_audience"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Snapshot of the canonical demonstration structure. Embedded (rather than
# imported) so this migration stays reproducible even if app data changes.
STRUCTURE = (
    (
        "DSTU",
        "Донской государственный технический университет",
        (
            (
                "FIST",
                "ФИСТ",
                (
                    ("PMI", "ПМИ", (("IVT-21", "ИВТ-21"), ("IVT-31", "ИВТ-31"), ("IVT-41", "ИВТ-41"))),
                    ("IS", "ИС", (("FIST-31", "ФИСТ-31"), ("FIST-21", "ФИСТ-21"))),
                ),
            ),
            (
                "IOT",
                "ИОТ",
                (("PMI-IOT", "ПМИ", (("IOT-IVT-31", "ИВТ-31"), ("IOT-IVT-41", "ИВТ-41"))),),
            ),
            ("LAW", "Юрфак", (("LAW-PR", "Право", (("UR-31", "ЮР-31"),)),)),
        ),
    ),
    (
        "SFEDU",
        "Южный федеральный университет",
        (
            (
                "SFEDU-IOT",
                "ИОТ",
                (("SFEDU-IOT-PMI", "ПМИ", (("SFEDU-IVT-31", "ИВТ-31"),)),),
            ),
        ),
    ),
)


def _normalise(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(value.strip().casefold().replace("ё", "е").split())
    return collapsed or None


def upgrade() -> None:
    op.create_table(
        "universities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_universities_id"), "universities", ["id"])
    op.create_index(op.f("ix_universities_code"), "universities", ["code"], unique=True)

    op.create_table(
        "faculties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("university_id", "name", name="uq_faculties_university_name"),
    )
    op.create_index(op.f("ix_faculties_id"), "faculties", ["id"])
    op.create_index(op.f("ix_faculties_university_id"), "faculties", ["university_id"])

    op.create_table(
        "study_programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("faculty_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["faculty_id"], ["faculties.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("faculty_id", "name", name="uq_study_programs_faculty_name"),
    )
    op.create_index(op.f("ix_study_programs_id"), "study_programs", ["id"])
    op.create_index(op.f("ix_study_programs_faculty_id"), "study_programs", ["faculty_id"])

    op.create_table(
        "study_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("study_program_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["study_program_id"], ["study_programs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint(
            "study_program_id", "name", name="uq_study_groups_program_name"
        ),
    )
    op.create_index(op.f("ix_study_groups_id"), "study_groups", ["id"])
    op.create_index(
        op.f("ix_study_groups_study_program_id"), "study_groups", ["study_program_id"]
    )

    op.add_column(
        "student_profiles", sa.Column("study_group_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "student_profiles",
        sa.Column("legacy_context", postgresql.JSONB(), nullable=True),
    )
    op.create_foreign_key(
        "fk_student_profiles_study_group_id",
        "student_profiles",
        "study_groups",
        ["study_group_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_student_profiles_study_group_id"),
        "student_profiles",
        ["study_group_id"],
    )
    bind = op.get_bind()

    # --- seed canonical structure -------------------------------------------
    universities: dict[str, int] = {}
    faculties: dict[str, int] = {}
    programs: dict[str, int] = {}
    # (normalised group name) -> list of (group_id, uni_name, faculty_name, program_name)
    groups_by_name: dict[str, list[tuple[int, str, str, str]]] = {}

    for uni_code, uni_name, faculty_list in STRUCTURE:
        uni_id = bind.execute(
            sa.text(
                "INSERT INTO universities (code, name) VALUES (:code, :name) "
                "RETURNING id"
            ),
            {"code": uni_code, "name": uni_name},
        ).scalar_one()
        universities[uni_code] = uni_id
        for fac_code, fac_name, program_list in faculty_list:
            fac_id = bind.execute(
                sa.text(
                    "INSERT INTO faculties (university_id, code, name) "
                    "VALUES (:university_id, :code, :name) RETURNING id"
                ),
                {"university_id": uni_id, "code": fac_code, "name": fac_name},
            ).scalar_one()
            faculties[fac_code] = fac_id
            for prog_code, prog_name, group_list in program_list:
                prog_id = bind.execute(
                    sa.text(
                        "INSERT INTO study_programs (faculty_id, code, name) "
                        "VALUES (:faculty_id, :code, :name) RETURNING id"
                    ),
                    {"faculty_id": fac_id, "code": prog_code, "name": prog_name},
                ).scalar_one()
                programs[prog_code] = prog_id
                for group_code, group_name in group_list:
                    group_id = bind.execute(
                        sa.text(
                            "INSERT INTO study_groups (study_program_id, code, name) "
                            "VALUES (:study_program_id, :code, :name) RETURNING id"
                        ),
                        {
                            "study_program_id": prog_id,
                            "code": group_code,
                            "name": group_name,
                        },
                    ).scalar_one()
                    groups_by_name.setdefault(_normalise(group_name), []).append(
                        (group_id, uni_name, fac_name, prog_name)
                    )

    # --- migrate existing profiles ------------------------------------------
    rows = list(
        bind.execute(
            sa.text(
                "SELECT user_id, university, faculty, course, study_group, study_program "
                "FROM student_profiles"
            )
        ).mappings()
    )

    for row in rows:
        legacy = {
            "university": row["university"],
            "faculty": row["faculty"],
            "course": row["course"],
            "study_group": row["study_group"],
            "study_program": row["study_program"],
        }
        original = {
            key: value for key, value in legacy.items() if value not in (None, "")
        }
        updates: dict[str, object] = {}

        group_key = _normalise(row["study_group"])
        matched: int | None = None
        if group_key is not None:
            candidates = groups_by_name.get(group_key, [])
            uni_key = _normalise(row["university"])
            fac_key = _normalise(row["faculty"])
            prog_key = _normalise(row["study_program"])

            def consistent(candidate):
                _, uni_name, fac_name, prog_name = candidate
                checks = (
                    (uni_key, _normalise(uni_name)),
                    (fac_key, _normalise(fac_name)),
                    (prog_key, _normalise(prog_name)),
                )
                return all(
                    provided is None or provided == canonical
                    for provided, canonical in checks
                )

            filtered = [candidate for candidate in candidates if consistent(candidate)]
            if len(filtered) == 1:
                matched = filtered[0][0]

        if matched is not None:
            updates["study_group_id"] = matched

        course = row["course"]
        if course is not None and not (1 <= course <= 6):
            # The DB constraint only allows 1..6. Never invent a course: keep
            # the original value in the snapshot and leave the column empty.
            updates["course"] = None

        if original:
            # Always keep a lossless snapshot of the Sprint 2 values. Legacy
            # columns are left untouched as well, but the snapshot survives
            # later profile edits and is what the clarification report reads.
            updates["legacy_context"] = json.dumps(original, ensure_ascii=False)

        if updates:
            assignments = []
            for column in updates:
                if column == "legacy_context":
                    assignments.append(f"{column} = CAST(:{column} AS jsonb)")
                else:
                    assignments.append(f"{column} = :{column}")
            params = dict(updates)
            params["user_id"] = row["user_id"]
            bind.execute(
                sa.text(
                    "UPDATE student_profiles SET "
                    + ", ".join(assignments)
                    + " WHERE user_id = :user_id"
                ),
                params,
            )

    # Added only after out-of-range values were moved to ``legacy_context``, so
    # upgrading a Sprint 2 database cannot fail on pre-existing data.
    op.create_check_constraint(
        "ck_student_profiles_course_range",
        "student_profiles",
        "course IS NULL OR (course >= 1 AND course <= 6)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_student_profiles_course_range", "student_profiles", type_="check"
    )
    bind = op.get_bind()
    # Restore out-of-range course values that were preserved during upgrade.
    bind.execute(
        sa.text(
            "UPDATE student_profiles "
            "SET course = (legacy_context->>'course')::integer "
            "WHERE course IS NULL "
            "AND legacy_context ? 'course' "
            "AND jsonb_typeof(legacy_context->'course') = 'number'"
        )
    )
    op.drop_index(
        op.f("ix_student_profiles_study_group_id"), table_name="student_profiles"
    )
    op.drop_constraint(
        "fk_student_profiles_study_group_id", "student_profiles", type_="foreignkey"
    )
    op.drop_column("student_profiles", "legacy_context")
    op.drop_column("student_profiles", "study_group_id")

    op.drop_index(op.f("ix_study_groups_study_program_id"), table_name="study_groups")
    op.drop_index(op.f("ix_study_groups_id"), table_name="study_groups")
    op.drop_table("study_groups")
    op.drop_index(op.f("ix_study_programs_faculty_id"), table_name="study_programs")
    op.drop_index(op.f("ix_study_programs_id"), table_name="study_programs")
    op.drop_table("study_programs")
    op.drop_index(op.f("ix_faculties_university_id"), table_name="faculties")
    op.drop_index(op.f("ix_faculties_id"), table_name="faculties")
    op.drop_table("faculties")
    op.drop_index(op.f("ix_universities_code"), table_name="universities")
    op.drop_index(op.f("ix_universities_id"), table_name="universities")
    op.drop_table("universities")
