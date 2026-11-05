"""Schedule routes backed by canonical StudyGroup IDs."""
from datetime import date

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.schedule import staff_schedule_groups
from app.models.user import User
from app.schemas.schedule import GroupSelector, ScheduleAccessGrant, ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services.university import context_from_group
from app.services.schedule import (
    create_schedule, ensure_schedule_access, get_student_group_id,
    group_key, list_schedule, resolve_schedule_group, update_schedule,
)

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/me", response_model=list[ScheduleRead])
async def my_schedule(
    day: date | None = Query(None, alias="date"),
    week: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group_id = await get_student_group_id(db, user)
    return await list_schedule(db, group_id, day=day, week=week)


@router.get("/group", response_model=list[ScheduleRead])
async def group_schedule(
    study_group_id: int = Query(gt=0),
    day: date | None = Query(None, alias="date"),
    week: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("staff", "admin")),
):
    await resolve_schedule_group(db, study_group_id)
    await ensure_schedule_access(db, user, study_group_id)
    return await list_schedule(db, study_group_id, day=day, week=week)


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
async def add_schedule(
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("staff", "admin")),
):
    return await create_schedule(db, user, payload)


@router.patch("/{entry_id}", response_model=ScheduleRead)
async def patch_schedule(
    entry_id: int,
    payload: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("staff", "admin")),
):
    return await update_schedule(db, user, entry_id, payload)


@router.post("/access/grant", status_code=status.HTTP_204_NO_CONTENT)
async def grant_group_permission(
    payload: ScheduleAccessGrant,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    staff = await db.get(User, payload.staff_id)
    if staff is None or staff.role != "staff":
        raise HTTPException(status_code=404, detail="Staff user not found")
    group = await resolve_schedule_group(db, payload.study_group_id)
    key = group_key(GroupSelector(**context_from_group(group)))
    # The legacy (staff_id, group_key) PK must still be populated until Commit 3.
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    await db.execute(
        insert(staff_schedule_groups)
        .values(staff_id=staff.id, group_key=key, study_group_id=group.id)
        .on_conflict_do_update(
            index_elements=["staff_id", "group_key"],
            set_={"study_group_id": group.id},
        )
    )
    await db.commit()
