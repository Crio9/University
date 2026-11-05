from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import StaffProfile, StudentProfile, TeacherProfile
from app.models.student_interest import student_interests
from app.models.university import Faculty, StudyGroup, StudyProgram
from app.models.user import User
from app.services.university import load_profile, student_context
from app.schemas.profile import (
    StaffProfileUpdate,
    StudentProfileUpdate,
    TeacherProfileUpdate,
)


async def read_profile(db: AsyncSession, current_user: User) -> dict:
    profile_data = {}
    if current_user.role == "student":
        st = await load_profile(db, current_user.id)
        context = student_context(st) if st is not None else None
        interests_res = await db.execute(
            select(student_interests.c.tag_id).where(
                student_interests.c.student_id == current_user.id
            )
        )
        interest_ids = list(interests_res.scalars().all())
        profile_data = {
            "university": context.university if context else None,
            "faculty": context.faculty if context else None,
            "course": context.course if context else None,
            "study_group": context.group if context else None,
            "study_program": context.program if context else None,
            "study_group_id": st.study_group_id if st else None,
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

    if data.study_group_id is not None:
        group = await db.scalar(
            select(StudyGroup)
            .where(StudyGroup.id == data.study_group_id)
            .options(
                selectinload(StudyGroup.program)
                .selectinload(StudyProgram.faculty)
                .selectinload(Faculty.university)
            )
        )
        if group is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown study group",
            )
        profile.study_group_id = group.id
        program = group.program
        profile.university = program.faculty.university.name
        profile.faculty = program.faculty.name
        profile.study_program = program.name
        profile.study_group = group.name
    elif any(value.strip() for value in (data.university, data.faculty, data.study_group, data.study_program)):
        # Kept for Sprint 2 clients that send text only; the canonical group
        # is not known yet, so the migration rule (FR-1.7) is not violated by
        # the row itself until a group is selected.
        profile.university = data.university
        profile.faculty = data.faculty
        profile.study_group = data.study_group
        profile.study_program = data.study_program

    if data.course is not None:
        profile.course = data.course

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
    await db.refresh(profile, attribute_names=["study_group"])

    return {
        "message": "Student profile updated",
        "profile": {
            "university": profile.university,
            "faculty": profile.faculty,
            "course": profile.course,
            "study_group": profile.study_group,
            "study_program": profile.study_program,
            "study_group_id": profile.study_group_id,
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
