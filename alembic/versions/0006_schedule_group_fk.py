"""Attach schedule entries and staff grants to canonical study_groups.

Revision ID: 0006_schedule_group_fk
Revises: 0005_merge_s3

Expand/backfill migration. No row is dropped and the old group_key and
text fields stay intact. Ambiguous / unknown legacy contexts remain NULL;
review them before removing the compatibility columns in a later release.
"""

from __future__ import annotations

import hashlib
import json
from itertools import product
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_schedule_group_fk"
down_revision: Union[str, None] = "0005_merge_s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# This is a snapshot of the known Sprint 3 aliases. Keep migrations independent
# of app/core/university.py because its catalogue may change after deployment.
_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "university": {
        "DSTU": ("ДГТУ", "Донской государственный технический университет", "DSTU"),
        "SFEDU": ("ЮФУ", "Южный федеральный университет", "SFEDU"),
    },
    "faculty": {
        "FIST": ("ФИТ", "ФИСТ", "Факультет информационных систем и технологий"),
        "IOT": ("ИОТ", "Институт опережающих технологий"),
        "LAW": ("Юрфак", "Юридический факультет"),
        "SFEDU-IOT": ("ИОТ", "ИОТ ЮФУ", "Институт опережающих технологий ЮФУ"),
    },
    "program": {
        "PMI": ("ПМИ", "Прикладная математика и информатика"),
        "IS": ("ИС", "Информационные системы"),
        "PMI-IOT": ("ПМИ", "ПМИ ИОТ", "Прикладная математика и информатика (ИОТ)"),
        "LAW-PR": ("Право", "Юриспруденция"),
        "SFEDU-IOT-PMI": ("ПМИ", "ПМИ ЮФУ", "Прикладная математика и информатика (ЮФУ)"),
    },
    "group": {
        "IOT-IVT-31": ("ИВТ-31", "ИОТ-31"),
        "IOT-IVT-41": ("ИВТ-41", "ИОТ-41"),
        "SFEDU-IVT-31": ("ИВТ-31", "ЮФУ-ИВТ-31"),
    },
}


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().replace("ё", "е").split())


def _names(dimension: str, code: str, db_name: str) -> tuple[str, ...]:
    names = (db_name, code, *_ALIASES[dimension].get(code, ()))
    return tuple(sorted({_norm(n) for n in names if _norm(n)}))


def _matches(value: str | None, *, dimension: str, code: str, name: str) -> bool:
    needle = _norm(value)
    return not needle or needle in _names(dimension, code, name)


def _lookup_group(record: dict, groups: list[dict]) -> int | None:
    """Resolve only a UNIQUE match from the entire university hierarchy.

    Never guess from a repeated group name. Missing contextual fields narrow
    the match less, so they may produce ambiguity and an unresolved NULL.
    """
    if not _norm(record.get("study_group")):
        return None
    matched = []
    for group in groups:
        if (
            _matches(record.get("university"), dimension="university",
                     code=group["university_code"], name=group["university_name"])
            and _matches(record.get("faculty"), dimension="faculty",
                         code=group["faculty_code"], name=group["faculty_name"])
            and _matches(record.get("study_program"), dimension="program",
                         code=group["program_code"], name=group["program_name"])
            and _matches(record.get("study_group"), dimension="group",
                         code=group["group_code"], name=group["group_name"])
        ):
            matched.append(group["group_id"])
    return matched[0] if len(matched) == 1 else None


def _legacy_key(parts: tuple[str, str, str, str]) -> str:
    """Mirror the old Schedule SHA256 key algorithm (without app imports)."""
    normalized = [_norm(part) for part in parts]
    return hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False).encode()
    ).hexdigest()


def _candidate_keys(group: dict) -> set[str]:
    """Common legacy hashes from canonical/alias names.

    A hash cannot be reversed. We generate only known valid spellings; all
    other grants without a schedule record remain NULL for manual review.
    """
    dims = (
        _names("university", group["university_code"], group["university_name"]),
        _names("faculty", group["faculty_code"], group["faculty_name"]),
        _names("program", group["program_code"], group["program_name"]),
        _names("group", group["group_code"], group["group_name"]),
    )
    return {_legacy_key(parts) for parts in product(*dims)}


def _get_groups(bind) -> list[dict]:
    query = sa.text("""
        SELECT g.id AS group_id, g.code AS group_code, g.name AS group_name,
               p.code AS program_code, p.name AS program_name,
               f.code AS faculty_code, f.name AS faculty_name,
               u.code AS university_code, u.name AS university_name
        FROM study_groups AS g
        JOIN study_programs AS p ON p.id = g.study_program_id
        JOIN faculties AS f ON f.id = p.faculty_id
        JOIN universities AS u ON u.id = f.university_id
        ORDER BY g.id
    """)
    return [dict(row) for row in bind.execute(query).mappings()]


def upgrade() -> None:
    op.add_column(
        "schedule_entries", sa.Column("study_group_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_schedule_entries_study_group_id", "schedule_entries", "study_groups",
        ["study_group_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "ix_schedule_group_id_start", "schedule_entries", ["study_group_id", "starts_at"]
    )
    op.create_index(
        "ix_schedule_group_id_original", "schedule_entries",
        ["study_group_id", "original_starts_at"],
    )

    op.add_column(
        "staff_schedule_groups", sa.Column("study_group_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_staff_schedule_groups_study_group_id", "staff_schedule_groups", "study_groups",
        ["study_group_id"], ["id"], ondelete="RESTRICT",
    )
    # PostgreSQL permits multiple NULLs in a UNIQUE constraint. Duplicate
    # aliases for one group must not cause a failed migration.
    op.create_unique_constraint(
        "uq_staff_schedule_groups_staff_group_id", "staff_schedule_groups",
        ["staff_id", "study_group_id"],
    )

    bind = op.get_bind()
    groups = _get_groups(bind)

    # Backfill schedule, preserving every original text and group_key value.
    # group_key -> set(group_id) is also useful for pre-existing staff grants.
    key_candidates: dict[str, set[int]] = {}
    schedule_rows = bind.execute(sa.text("""
        SELECT id, group_key, university, faculty, study_program, study_group
        FROM schedule_entries WHERE study_group_id IS NULL
    """)).mappings()
    for row in schedule_rows:
        record = dict(row)
        matched_id = _lookup_group(record, groups)
        if matched_id is None:
            continue
        bind.execute(
            sa.text("UPDATE schedule_entries SET study_group_id=:group_id WHERE id=:id"),
            {"group_id": matched_id, "id": record["id"]},
        )
        # A staff grant must never inherit access from a corrupted or manually
        # altered legacy key on a schedule row.
        original_parts = tuple(record[field] for field in (
            "university", "faculty", "study_program", "study_group"
        ))
        if _legacy_key(original_parts) == record["group_key"]:
            key_candidates.setdefault(record["group_key"], set()).add(matched_id)

    # Only grant access when a legacy hash identifies EXACTLY one canonical
    # group. Build a safe lookup from known spellings as well as scheduled rows.
    for group in groups:
        for key in _candidate_keys(group):
            key_candidates.setdefault(key, set()).add(group["group_id"])

    staff_rows = list(bind.execute(sa.text("""
        SELECT staff_id, group_key FROM staff_schedule_groups
        WHERE study_group_id IS NULL ORDER BY staff_id, group_key
    """)).mappings())
    assigned = {
        (row["staff_id"], row["study_group_id"])
        for row in bind.execute(sa.text("""
            SELECT staff_id, study_group_id FROM staff_schedule_groups
            WHERE study_group_id IS NOT NULL
        """)).mappings()
    }
    for row in staff_rows:
        candidates = key_candidates.get(row["group_key"], set())
        if len(candidates) != 1:
            continue
        group_id = next(iter(candidates))
        pair = (row["staff_id"], group_id)
        if pair in assigned:
            continue  # Retain a duplicate legacy row with NULL FK for review.
        bind.execute(sa.text("""
            UPDATE staff_schedule_groups SET study_group_id=:group_id
            WHERE staff_id=:staff_id AND group_key=:group_key
        """), {"group_id": group_id, "staff_id": row["staff_id"],
               "group_key": row["group_key"]})
        assigned.add(pair)


def downgrade() -> None:
    """Drop only the new FK columns; original schedule and grant data remain."""
    op.drop_constraint(
        "uq_staff_schedule_groups_staff_group_id", "staff_schedule_groups", type_="unique"
    )
    op.drop_constraint(
        "fk_staff_schedule_groups_study_group_id", "staff_schedule_groups", type_="foreignkey"
    )
    op.drop_column("staff_schedule_groups", "study_group_id")
    op.drop_index("ix_schedule_group_id_original", table_name="schedule_entries")
    op.drop_index("ix_schedule_group_id_start", table_name="schedule_entries")
    op.drop_constraint(
        "fk_schedule_entries_study_group_id", "schedule_entries", type_="foreignkey"
    )
    op.drop_column("schedule_entries", "study_group_id")
