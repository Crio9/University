from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.schemas.profile import (
    StaffProfileUpdate,
    StudentProfileUpdate,
    TeacherProfileUpdate,
)
from app.services.profiles import read_profile, update_profile

router = APIRouter(prefix="/profile", tags=["profiles"])


@router.get("/me")
def get_my_profile(current_user: dict = Depends(get_current_user)):
    return read_profile(current_user)


@router.put("/student")
def update_student(
    data: StudentProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    return update_profile("student", data, current_user)


@router.put("/teacher")
def update_teacher(
    data: TeacherProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    return update_profile("teacher", data, current_user)


@router.put("/staff")
def update_staff(
    data: StaffProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    return update_profile("staff", data, current_user)
