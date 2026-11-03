"""Canonical audience values come from the canonical university structure.

Legacy profile text is still accepted for profiles that were not linked to a
``StudyGroup`` during the Sprint 3 migration, so Sprint 2 targeting keeps
working. For linked profiles the group's canonical chain is the only source of
truth (FR-1.6).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import StudentProfile
from app.models.university import Faculty, StudyGroup, StudyProgram
from app.schemas.ai_classification import TargetAudience
from app.services.university import (
    audience_key,
    context_from_group,
    load_canonical_names,
)


async def normalize_audience(
    db: AsyncSession, audience: TargetAudience | dict
):
    """Resolve AI-provided audience values to canonical display names.

    Values are matched against canonical names and declared aliases. Unresolved
    values are reported to the caller (leading to ``needs_review``), never
    silently dropped (B-08 / FR-2.8).
    """
    if isinstance(audience, TargetAudience):
        data = audience.model_dump()
    else:
        data = {
            "faculty": [],
            "program": [],
            "course": [],
            "group": [],
            **audience,
        }

    canonical = await load_canonical_names(db)
    unresolved = []
    for field in ("faculty", "program", "group"):
        requested = data[field]
        if not requested:
            continue
        candidates = getattr(canonical, {"faculty": "faculties", "program": "programs", "group": "groups"}[field])
        resolved = []
        for value in requested:
            key = audience_key(value)
            matches = [
                name
                for name, aliases in candidates.items()
                if key in {audience_key(alias) for alias in aliases}
            ]
            if len(matches) != 1:
                unresolved.append(f"{field}={value}")
                continue
            display = candidates[matches[0]][0]
            if display not in resolved:
                resolved.append(display)
        data[field] = resolved
    return TargetAudience.model_validate(data), unresolved


def matches_audience(audience: dict | None, profile: StudentProfile) -> bool:
    if audience is None:
        return True

    # A linked group defines the whole context (FR-1.6); legacy text is the
    # fallback for profiles that were left unlinked by the migration.
    if profile.study_group_id is not None:
        group = profile.study_group
        if group is None:
            return False
        derived = context_from_group(group)
        faculty = derived["faculty"]
        program = derived["study_program"]
        group_name = derived["study_group"]
    else:
        faculty = profile.faculty
        program = profile.study_program
        group_name = profile.study_group

    values = {
        "faculty": faculty,
        "program": program,
        "course": profile.course,
        "group": group_name,
    }
    for field, value in values.items():
        allowed = audience.get(field, [])
        if not allowed:
            continue
        if value is None:
            return False
        if field == "course":
            if value not in allowed:
                return False
        elif audience_key(value) not in {audience_key(item) for item in allowed}:
            return False
    return True


def synchronize_targeting(data: dict, current=None) -> dict:
    """Keep legacy scalar fields usable without discarding group restrictions."""
    fields = {
        "target_faculty": "faculty",
        "target_program": "program",
        "target_course": "course",
    }
    if (
        "target_audience" not in data
        and current is not None
        and current.target_audience
    ):
        changes = {key: value for key, value in data.items() if key in fields}
        if changes:
            audience = {
                key: list(value) for key, value in current.target_audience.items()
            }
            for key, value in changes.items():
                audience[fields[key]] = [value] if value is not None else []
            data["target_audience"] = audience
    if data.get("target_audience") is not None:
        for scalar, dimension in fields.items():
            values = data["target_audience"][dimension]
            data[scalar] = values[0] if len(values) == 1 else None
    elif "target_audience" in data and current is not None:
        for scalar in fields:
            data.setdefault(scalar, None)
    return data
