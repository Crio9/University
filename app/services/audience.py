"""Canonical audience values come from the existing university profiles."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import StudentProfile
from app.schemas.ai_classification import TargetAudience


def audience_key(value: str) -> str:
    return " ".join(value.strip().casefold().replace("ё", "е").split())


async def normalize_audience(db: AsyncSession, audience: TargetAudience):
    data = audience.model_dump()
    unresolved = []
    for field, column in (
        ("faculty", StudentProfile.faculty),
        ("program", StudentProfile.study_program),
        ("group", StudentProfile.study_group),
    ):
        if not data[field]:
            continue
        rows = await db.scalars(
            select(column).where(column.is_not(None)).distinct().order_by(column)
        )
        references = {}

        values = sorted(
            {value.strip() for value in rows if value.strip()},
            key=lambda value: (
                value != value.upper(),
                value.casefold(),
                value,
            ),
        )

        for value in values:
            references.setdefault(audience_key(value), value)
        canonical = []
        for value in data[field]:
            match = references.get(audience_key(value))
            if match is None:
                unresolved.append(f"{field}={value}")
            elif match not in canonical:
                canonical.append(match)
        data[field] = canonical
    return TargetAudience.model_validate(data), unresolved


def matches_audience(audience: dict | None, profile: StudentProfile) -> bool:
    if audience is None:
        return True
    for field, value in (
        ("faculty", profile.faculty),
        ("program", profile.study_program),
        ("course", profile.course),
        ("group", profile.study_group),
    ):
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
