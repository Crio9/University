from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.dictionaries import Tag
from app.models.user import User, UserRole
from app.schemas.profile import (
    ProfileMeRead,
    StaffProfileRead,
    StaffProfileUpdate,
    StudentProfileRead,
    StudentProfileUpdate,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileMeRead)
def get_my_profile(current_user: User = Depends(get_current_user)) -> ProfileMeRead:
    return ProfileMeRead(
        user_id=current_user.id,
        email=current_user.email,
        role=current_user.role.value,
        student_profile=(
            StudentProfileRead.model_validate(current_user.student_profile)
            if current_user.student_profile
            else None
        ),
        staff_profile=(
            StaffProfileRead.model_validate(current_user.staff_profile)
            if current_user.staff_profile
            else None
        ),
    )


@router.patch("/me/student", response_model=ProfileMeRead)
def update_student_profile(
    data: StudentProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileMeRead:
    if current_user.role != UserRole.STUDENT or current_user.student_profile is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student profile required")

    profile = current_user.student_profile
    payload = data.model_dump(exclude_unset=True)
    interest_ids = payload.pop("interest_tag_ids", None)

    for field, value in payload.items():
        setattr(profile, field, value)

    if interest_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(interest_ids)).all()
        if len(tags) != len(set(interest_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown tag id")
        profile.interests = tags

    db.commit()
    db.refresh(current_user)
    return get_my_profile(current_user)


@router.patch("/me/staff", response_model=ProfileMeRead)
def update_staff_profile(
    data: StaffProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileMeRead:
    if current_user.role not in (UserRole.STAFF, UserRole.ADMIN) or current_user.staff_profile is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff profile required")

    profile = current_user.staff_profile
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(current_user)
    return get_my_profile(current_user)
