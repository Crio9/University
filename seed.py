import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal, engine
from app.models.dictionaries import Category, Tag
from app.models.post import Post
from app.models.profile import StaffProfile, StudentProfile, TeacherProfile
from app.models.student_interest import student_interests
from app.models.user import User
from app.models.university import StudyGroup
from app.services.dictionaries import sync_reference_data
from app.services.university import sync_university_structure


async def seed_data():
    async with AsyncSessionLocal() as db:
        # Reconcile the canonical vocabulary (idempotent; reuses legacy rows).
        await sync_reference_data(db)
        # Canonical university structure (managed seed/import, FR-1.10).
        await sync_university_structure(db)
        await db.flush()

        # Use an existing canonical group; never invent a numeric group ID.
        demo_group = await db.scalar(
            select(StudyGroup).where(StudyGroup.code == "IVT-21")
        )
        if demo_group is None:
            raise RuntimeError("Canonical demo group IVT-21 was not seeded")

        cats_res = await db.execute(select(Category))
        categories = {cat.code: cat for cat in cats_res.scalars().all() if cat.code}
        tags_res = await db.execute(select(Tag))
        tags = {tag.code: tag for tag in tags_res.scalars().all() if tag.code}

        users_data = [
            {
                "email": "student@uni.test",
                "full_name": "Иван Студентов",
                "role": "student",
                "password": "password123",
            },
            {
                "email": "teacher@uni.test",
                "full_name": "Петр Преподавателев",
                "role": "teacher",
                "password": "password123",
            },
            {
                "email": "staff@uni.test",
                "full_name": "Анна Сотрудникова",
                "role": "staff",
                "password": "password123",
            },
        ]

        users = {}
        for udata in users_data:
            res = await db.execute(select(User).where(User.email == udata["email"]))
            user = res.scalar_one_or_none()
            if not user:
                user = User(
                    email=udata["email"],
                    full_name=udata["full_name"],
                    role=udata["role"],
                    password_hash=hash_password(udata["password"]),
                )
                db.add(user)
                await db.flush()
                if user.role == "student":
                    db.add(
                        StudentProfile(
                            user_id=user.id,
                            study_group_id=demo_group.id,
                            university="Донской государственный технический университет",
                            faculty="ФИТ",
                            course=2,
                            study_group="ИВТ-21",
                            study_program="ПМИ",
                        )
                    )
                    await db.flush()
                    await db.execute(
                        student_interests.insert().values(
                            [
                                {"student_id": user.id, "tag_id": tags["SCIENCE"].id},
                                {"student_id": user.id, "tag_id": tags["CAREER"].id},
                            ]
                        )
                    )
                elif user.role == "teacher":
                    db.add(
                        TeacherProfile(
                            user_id=user.id,
                            department="Кафедра ВТ",
                            academic_title="Доцент",
                            office="301-А",
                        )
                    )
                elif user.role == "staff":
                    db.add(
                        StaffProfile(
                            user_id=user.id,
                            department="Деканат",
                            position="Инспектор",
                        )
                    )
            # Re-running seed also fixes the old unlinked demo student.
            # Never overwrite a canonical group already chosen manually.
            if udata["role"] == "student" and user.role == "student":
                profile = await db.get(StudentProfile, user.id)
                if profile is None:
                    profile = StudentProfile(user_id=user.id)
                    db.add(profile)
                if profile.study_group_id is None:
                    profile.study_group_id = demo_group.id
                    profile.university = "Донской государственный технический университет"
                    profile.faculty = "ФИТ"
                    profile.study_program = "ПМИ"
                    profile.study_group = "ИВТ-21"
                    profile.course = profile.course or 2
            users[udata["role"]] = user

        now = datetime.now(timezone.utc)
        posts_data = [
            {
                "title": "Грант на ИТ-стартап",
                "content": "Подача заявок на получение гранта для студентов ИТ-направлений.",
                "summary": "Грант для студентов ИТ-направлений, заявки до 5 дней.",
                "category": categories["OPPORTUNITY"],
                "author_id": users["staff"].id,
                "importance": "standard",
                "deadline": now + timedelta(days=5),
                "target_faculty": "ФИСТ",
                "target_course": 2,
                "target_program": "ПМИ",
                "tags": [tags["SCIENCE"], tags["CAREER"]],
            },
            {
                "title": "Обходной лист выпускника",
                "content": "Сдача обходных листов перед защитой ВКР.",
                "summary": "Выпускникам необходимо сдать обходной лист перед защитой ВКР.",
                "category": categories["ADMINISTRATIVE"],
                "author_id": users["staff"].id,
                "importance": "standard",
                "deadline": None,
                "target_faculty": None,
                "target_course": 4,
                "target_program": None,
                "tags": [tags["DOCUMENTS"], tags["THESIS"]],
            },
            {
                "title": "День открытых дверей",
                "content": "Приглашаем всех на общеуниверситетский день открытых дверей.",
                "summary": "Общеуниверситетский день открытых дверей.",
                "category": categories["EVENT"],
                "author_id": users["staff"].id,
                "importance": "standard",
                "deadline": None,
                "target_faculty": None,
                "target_course": None,
                "target_program": None,
                "tags": [],
            },
            {
                "title": "Стипендия Правительства",
                "content": "Срочный прием документов на повышенную стипендию.",
                "summary": "Срочный приём документов на повышенную стипендию.",
                "category": categories["OPPORTUNITY"],
                "author_id": users["staff"].id,
                "importance": "critical",
                "deadline": now + timedelta(days=3),
                "target_faculty": None,
                "target_course": None,
                "target_program": None,
                "tags": [tags["SCHOLARSHIP"]],
            },
            {
                "title": "Хакатон по искусственному интеллекту",
                "content": "Соревнование по разработке ML-решений.",
                "summary": "Соревнование по разработке ML-решений.",
                "category": categories["EVENT"],
                "author_id": users["staff"].id,
                "importance": "high",
                "deadline": now + timedelta(days=10),
                "target_faculty": None,
                "target_course": None,
                "target_program": None,
                "tags": [tags["HACKATHON"], tags["SCIENCE"]],
            },
        ]

        for pdata in posts_data:
            res = await db.execute(select(Post).where(Post.title == pdata["title"]))
            if not res.scalar_one_or_none():
                post = Post(
                    title=pdata["title"],
                    content=pdata["content"],
                    summary=pdata.get("summary"),
                    category_id=pdata["category"].id,
                    author_id=pdata["author_id"],
                    importance=pdata["importance"],
                    deadline=pdata["deadline"],
                    target_faculty=pdata["target_faculty"],
                    target_course=pdata["target_course"],
                    target_program=pdata["target_program"],
                    tags=pdata["tags"],
                )
                db.add(post)

        await db.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())
