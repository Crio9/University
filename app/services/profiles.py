from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import StaffProfile, StudentProfile, TeacherProfile
from app.models.student_interest import student_interests
from app.models.user import User
from app.schemas.profile import (
    StaffProfileUpdate,
    StudentProfileUpdate,
    TeacherProfileUpdate,
)


async def read_profile(db: AsyncSession, current_user: User) -> dict:
    profile_data = {}
    if current_user.role == "student":
        res = await db.execute(
            select(StudentProfile).where(StudentProfile.user_id == current_user.id)
        )
        st = res.scalar_one_or_none()
        interests_res = await db.execute(
            select(student_interests.c.tag_id).where(
                student_interests.c.student_id == current_user.id
            )
        )
        interest_ids = list(interests_res.scalars().all())
        profile_data = {
            "university": st.university if st else None,
            "faculty": st.faculty if st else None,
            "course": st.course if st else None,
            "study_group": st.study_group if st else None,
            "study_program": st.study_program if st else None,
            "interest_ids": interest_ids,
        }
    elif current_user.role == "teacher":
        res = await db.execute(
            select(TeacherProfile).where(TeacherProfile.user_id == current_user.id)
        )
        tp = res.scalar_one_or_none()
        profile_data = {
            "department": tp.department if tp else None,
            "academic_title": tp.academic_title if tp else None,
            "office": tp.office if tp else None,
        }
    elif current_user.role == "staff":
        res = await db.execute(
            select(StaffProfile).where(StaffProfile.user_id == current_user.id)
        )
        sp = res.scalar_one_or_none()
        profile_data = {
            "department": sp.department if sp else None,
            "position": sp.position if sp else None,
        }

    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "profile": profile_data,
    }


async def update_student_profile(
    db: AsyncSession, current_user: User, data: StudentProfileUpdate
) -> dict:
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can update this profile",
        )

    res = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == current_user.id)
    )
    profile = res.scalar_one_or_none()
    if profile is None:
        profile = StudentProfile(user_id=current_user.id)
        db.add(profile)

    profile.university = data.university
    profile.faculty = data.faculty
    profile.course = data.course
    profile.study_group = data.study_group
    profile.study_program = data.study_program

    await db.execute(
        delete(student_interests).where(student_interests.c.student_id == current_user.id)
    )
    if data.interest_ids:
        for tag_id in data.interest_ids:
            await db.execute(
                student_interests.insert().values(
                    student_id=current_user.id,
                    tag_id=tag_id,
                )
            )

    await db.commit()
    await db.refresh(profile)

    return {
        "message": "Student profile updated",
        "profile": {
            "university": profile.university,
            "faculty": profile.faculty,
            "course": profile.course,
            "study_group": profile.study_group,
            "study_program": profile.study_program,
            "interest_ids": data.interest_ids,
        },
    }


async def update_teacher_profile(
    db: AsyncSession, current_user: User, data: TeacherProfileUpdate
) -> dict:
    if current_user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can update this profile",
        )

    res = await db.execute(
        select(TeacherProfile).where(TeacherProfile.user_id == current_user.id)
    )
    profile = res.scalar_one_or_none()
    if profile is None:
        profile = TeacherProfile(user_id=current_user.id)
        db.add(profile)

    profile.department = data.department
    profile.academic_title = data.academic_title
    profile.office = data.office

    await db.commit()
    await db.refresh(profile)

    return {
        "message": "Teacher profile updated",
        "profile": {
            "department": profile.department,
            "academic_title": profile.academic_title,
            "office": profile.office,
        },
    }


async def update_staff_profile(
    db: AsyncSession, current_user: User, data: StaffProfileUpdate
) -> dict:
    if current_user.role != "staff":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only staff can update this profile",
        )

    res = await db.execute(
        select(StaffProfile).where(StaffProfile.user_id == current_user.id)
    )
    profile = res.scalar_one_or_none()
    if profile is None:
        profile = StaffProfile(user_id=current_user.id)
        db.add(profile)

    profile.department = data.department
    profile.position = data.position

    await db.commit()
    await db.refresh(profile)

    return {
        "message": "Staff profile updated",
        "profile": {
            "department": profile.department,
            "position": profile.position,
        },
    }
