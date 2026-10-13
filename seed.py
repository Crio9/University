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


async def seed_data():
    async with AsyncSessionLocal() as db:
        category_names = ["Новости", "Административное", "Возможности"]
        categories = {}
        for name in category_names:
            res = await db.execute(select(Category).where(Category.name == name))
            cat = res.scalar_one_or_none()
            if not cat:
                cat = Category(name=name)
                db.add(cat)
                await db.flush()
            categories[name] = cat

        tag_names = [
            "Карьера",
            "ИТ",
            "Спорт",
            "Наука",
            "Волонтерство",
            "Стипендии",
            "Общежитие",
            "Документы",
            "Конференции",
            "Стажировки",
        ]
        tags = {}
        for name in tag_names:
            res = await db.execute(select(Tag).where(Tag.name == name))
            tag = res.scalar_one_or_none()
            if not tag:
                tag = Tag(name=name)
                db.add(tag)
                await db.flush()
            tags[name] = tag

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
                            university="МГУ",
                            faculty="ФИСТ",
                            course=2,
                            study_group="ИТ-201",
                            study_program="ПМИ",
                        )
                    )
                    await db.flush()
                    await db.execute(
                        student_interests.insert().values(
                            [
                                {"student_id": user.id, "tag_id": tags["ИТ"].id},
                                {"student_id": user.id, "tag_id": tags["Карьера"].id},
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
            users[udata["role"]] = user

        now = datetime.now(timezone.utc)
        posts_data = [
            {
                "title": "Грант на ИТ-стартап",
                "content": "Подача заявок на получение гранта для студентов ИТ-направлений.",
                "category": categories["Возможности"],
                "author_id": users["staff"].id,
                "importance": "standard",
                "deadline": now + timedelta(days=5),
                "target_faculty": "ФИСТ",
                "target_course": 2,
                "target_program": "ПМИ",
                "tags": [tags["ИТ"], tags["Карьера"]],
            },
            {
                "title": "Обходной лист выпускника",
                "content": "Сдача обходных листов перед защитой ВКР.",
                "category": categories["Административное"],
                "author_id": users["staff"].id,
                "importance": "standard",
                "deadline": None,
                "target_faculty": None,
                "target_course": 4,
                "target_program": None,
                "tags": [tags["Документы"]],
            },
            {
                "title": "День открытых дверей",
                "content": "Приглашаем всех на общеуниверситетский день открытых дверей.",
                "category": categories["Новости"],
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
                "category": categories["Возможности"],
                "author_id": users["staff"].id,
                "importance": "critical",
                "deadline": now + timedelta(days=3),
                "target_faculty": None,
                "target_course": None,
                "target_program": None,
                "tags": [tags["Стипендии"]],
            },
            {
                "title": "Хакатон по искусственному интеллекту",
                "content": "Соревнование по разработке ML-решений.",
                "category": categories["Возможности"],
                "author_id": users["staff"].id,
                "importance": "high",
                "deadline": now + timedelta(days=10),
                "target_faculty": None,
                "target_course": None,
                "target_program": None,
                "tags": [tags["ИТ"], tags["Наука"]],
            },
        ]

        for pdata in posts_data:
            res = await db.execute(select(Post).where(Post.title == pdata["title"]))
            if not res.scalar_one_or_none():
                post = Post(
                    title=pdata["title"],
                    content=pdata["content"],
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
