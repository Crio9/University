"""Schedule service using StudyGroup.id for identity and staff permissions.

Until Commit 3, group_key and text snapshots remain for old DB compatibility.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import StudentProfile
from app.models.schedule import ScheduleEntry, staff_schedule_groups
from app.models.user import User
from app.schemas.schedule import GroupSelector, ScheduleCreate, ScheduleUpdate
from app.services.university import context_from_group, load_group

LOCAL_TZ = ZoneInfo("Europe/Moscow")  # agreed MVP timezone; revisit for multiple universities


def group_key(group: GroupSelector | StudentProfile) -> str:
    """Legacy stable key used only for existing NOT NULL columns/backfill."""
    items = [getattr(group, key, None) for key in (
        "university", "faculty", "study_program", "study_group"
    )]
    if any(not isinstance(x, str) or not x.strip() for x in items):
        raise HTTPException(status_code=409, detail="PROFILE_INCOMPLETE: university context is required")
    normalized = [" ".join(value.strip().casefold().replace("ё", "е").split()) for value in items]
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False).encode()).hexdigest()


async def resolve_schedule_group(db: AsyncSession, study_group_id: int):
    """Validate group ID, returning ORM StudyGroup with its parents eager-loaded."""
    group = await load_group(db, study_group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Study group not found")
    return group


def legacy_group_key_from_entity(group) -> str:
    """Snapshot legacy key from canonical context, not untrusted client strings."""
    return group_key(GroupSelector(**context_from_group(group)))


def period_bounds(*, day: date | None = None, week: date | None = None) -> tuple[datetime, datetime]:
    if day is not None and week is not None:
        raise HTTPException(status_code=422, detail="Specify either date or week")
    if day is None and week is None:
        day = datetime.now(LOCAL_TZ).date()
    if week is not None:
        start_day = week - timedelta(days=week.weekday())
        days = 7
    else:
        start_day = day
        days = 1
    start = datetime.combine(start_day, time.min, tzinfo=LOCAL_TZ)
    end = datetime.combine(start_day + timedelta(days=days), time.min, tzinfo=LOCAL_TZ)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


async def ensure_schedule_access(db: AsyncSession, user: User, study_group_id: int) -> None:
    if user.role == "admin":
        return
    if user.role != "staff":
        raise HTTPException(status_code=403, detail="Staff or admin required")
    allowed = await db.scalar(
        select(staff_schedule_groups.c.study_group_id).where(
            staff_schedule_groups.c.staff_id == user.id,
            staff_schedule_groups.c.study_group_id == study_group_id,
        )
    )
    if allowed is None:
        raise HTTPException(status_code=403, detail="Not authorized for this study group")


async def get_student_group_id(db: AsyncSession, user: User) -> int:
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    profile = await db.get(StudentProfile, user.id)
    if profile is None or profile.study_group_id is None:
        raise HTTPException(status_code=409, detail="PROFILE_INCOMPLETE: select study_group_id")
    return profile.study_group_id


async def list_schedule(db: AsyncSession, study_group_id: int, *, day: date | None, week: date | None) -> list[ScheduleEntry]:
    start, end = period_bounds(day=day, week=week)
    result = await db.scalars(
        select(ScheduleEntry).where(
            ScheduleEntry.study_group_id == study_group_id,
            or_(
                and_(ScheduleEntry.starts_at < end, ScheduleEntry.ends_at > start),
                and_(ScheduleEntry.original_starts_at < end, ScheduleEntry.original_ends_at > start),
            ),
        ).order_by(ScheduleEntry.starts_at, ScheduleEntry.id)
    )
    rows = list(result.all())
    # When moved, show it in the original day as well as the destination day.
    def sort_key(row: ScheduleEntry):
        actual = row.starts_at.replace(tzinfo=timezone.utc) if row.starts_at.tzinfo is None else row.starts_at
        if row.original_starts_at is not None:
            previous = (row.original_starts_at.replace(tzinfo=timezone.utc)
                        if row.original_starts_at.tzinfo is None else row.original_starts_at)
            if start <= previous < end and not start <= actual < end:
                return previous, row.id
        return actual, row.id
    return sorted(rows, key=sort_key)


async def create_schedule(db: AsyncSession, user: User, payload: ScheduleCreate) -> ScheduleEntry:
    group = await resolve_schedule_group(db, payload.study_group_id)
    await ensure_schedule_access(db, user, group.id)
    context = context_from_group(group)
    # Old schema still requires these strings and group_key. They no longer
    # determine the identity of the group or grant authorization.
    item = ScheduleEntry(
        **payload.model_dump(),
        **context,
        group_key=legacy_group_key_from_entity(group),
        created_by=user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_schedule(db: AsyncSession, user: User, entry_id: int, payload: ScheduleUpdate) -> ScheduleEntry:
    row = await db.get(ScheduleEntry, entry_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule entry not found")
    if row.study_group_id is None:
        raise HTTPException(status_code=409, detail="UNMIGRATED_SCHEDULE: study_group_id is missing")
    await ensure_schedule_access(db, user, row.study_group_id)
    if row.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Cancelled lessons are immutable")

    values = payload.model_dump(exclude_unset=True)
    if any(value is None for key, value in values.items() if key in {"subject", "starts_at", "ends_at", "status"}):
        raise HTTPException(status_code=422, detail="Required fields cannot be null")
    desired = values.get("status", row.status)
    if desired == "NORMAL" and row.status == "MOVED":
        raise HTTPException(status_code=409, detail="Cannot reset moved lesson to NORMAL")
    changed_time = "starts_at" in values or "ends_at" in values
    if changed_time and desired != "MOVED":
        raise HTTPException(status_code=422, detail="Time changes require status MOVED")
    if desired == "CANCELLED" and changed_time:
        raise HTTPException(status_code=422, detail="Cancel separately, without changing time")
    if desired == "MOVED" and row.status == "NORMAL":
        if not ("starts_at" in values and "ends_at" in values):
            raise HTTPException(status_code=422, detail="Moving a lesson requires both new times")
        row.original_starts_at = row.starts_at
        row.original_ends_at = row.ends_at
    if desired == "MOVED" and row.status == "MOVED" and changed_time:
        if not ("starts_at" in values and "ends_at" in values):
            raise HTTPException(status_code=422, detail="Provide both new times")
    for field, value in values.items():
        setattr(row, field, value)
    def aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if aware(row.ends_at) <= aware(row.starts_at):
        raise HTTPException(status_code=422, detail="starts_at must precede ends_at")
    if row.status == "MOVED" and row.original_starts_at is not None:
        if aware(row.starts_at) == aware(row.original_starts_at) and aware(row.ends_at) == aware(row.original_ends_at):
            raise HTTPException(status_code=422, detail="New time must differ from original")
    row.changed_by = user.id
    await db.commit()
    await db.refresh(row)
    return row
