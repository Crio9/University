from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.profile import (
    StaffProfileUpdate,
    StudentProfileUpdate,
    TeacherProfileUpdate,
)
from app.services.profiles import (
    read_profile,
    update_staff_profile,
    update_student_profile,
    update_teacher_profile,
)

router = APIRouter(prefix="/profile", tags=["profiles"])


@router.get("/me")
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await read_profile(db, current_user)


@router.put("/student")
async def update_student(
    data: StudentProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_student_profile(db, current_user, data)


@router.put("/teacher")
async def update_teacher(
    data: TeacherProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_teacher_profile(db, current_user, data)


@router.put("/staff")
async def update_staff(
    data: StaffProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_staff_profile(db, current_user, data)
