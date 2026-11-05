"""REST API for schedule on the develop branch."""
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
from app.services.schedule import (
    create_schedule, ensure_schedule_access, get_student_key, group_key,
    list_schedule, update_schedule,
)

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/me", response_model=list[ScheduleRead])
async def my_schedule(
    day: date | None = Query(None, alias="date"),
    week: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    key = await get_student_key(db, user)
    return await list_schedule(db, key, day=day, week=week)


@router.get("/group", response_model=list[ScheduleRead])
async def group_schedule(
    university: str,
    faculty: str,
    study_program: str,
    study_group: str,
    day: date | None = Query(None, alias="date"),
    week: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("staff", "admin")),
):
    group = GroupSelector(
        university=university, faculty=faculty,
        study_program=study_program, study_group=study_group,
    )
    key = group_key(group)
    await ensure_schedule_access(db, user, key)
    return await list_schedule(db, key, day=day, week=week)


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
    key = group_key(payload)
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    await db.execute(
        insert(staff_schedule_groups).values(staff_id=staff.id, group_key=key)
        .on_conflict_do_nothing(index_elements=["staff_id", "group_key"])
    )
    await db.commit()
