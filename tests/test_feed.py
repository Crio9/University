
import pytest
from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app as fastapi_app
from app.db.base import Base
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.post import Post, post_tags
from app.models.dictionaries import Category, Tag
from app.models.student_interest import student_interests


@pytest.mark.asyncio
async def test_feed_filters_posts_for_different_students():
    # Загружаем модели, чтобы SQLAlchemy увидел все таблицы.
    import app.models.profile
    import app.models.post
    import app.models.dictionaries
    import app.models.student_interest

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as db:
            student_it = User(
                email="it@example.test",
                password_hash="test-hash",
                full_name="Студент ИТ",
                role="student",
            )
            student_graduation = User(
                email="graduate@example.test",
                password_hash="test-hash",
                full_name="Выпускник",
                role="student",
            )
            admin = User(
                email="admin@example.test",
                password_hash="test-hash",
                full_name="Администратор",
                role="admin",
            )

            db.add_all([student_it, student_graduation, admin])
            await db.flush()

            db.add_all([
                StudentProfile(
                    user_id=student_it.id,
                    faculty="ИТ",
                    course=2,
                    study_program="Системный анализ",
                ),
                StudentProfile(
                    user_id=student_graduation.id,
                    faculty="Экономика",
                    course=4,
                    study_program="Экономика",
                ),
            ])

            grant_category = Category(name="Возможности")
            admin_category = Category(name="Административные объявления")
            startup_tag = Tag(name="стартапы")

            db.add_all([
                grant_category,
                admin_category,
                startup_tag,
            ])
            await db.flush()

            grant = Post(
                title="Грант на ИТ-стартап",
                content="Приём заявок на грант",
                category_id=grant_category.id,
                author_id=admin.id,
                importance="standard",
                deadline=datetime.now(timezone.utc) + timedelta(days=5),
                target_faculty="ИТ",
                target_course=2,
                target_program="Системный анализ",
            )

            graduation = Post(
                title="Обходной лист выпускника",
                content="Информация для выпускников",
                category_id=admin_category.id,
                author_id=admin.id,
                importance="standard",
                target_course=4,
            )

            db.add_all([grant, graduation])
            await db.flush()

            await db.execute(
                student_interests.insert().values(
                    student_id=student_it.id,
                    tag_id=startup_tag.id,
                )
            )

            await db.execute(
                post_tags.insert().values(
                    post_id=grant.id,
                    tag_id=startup_tag.id,
                )
            )

            await db.commit()

            it_user_id = student_it.id
            graduate_user_id = student_graduation.id

        async def override_get_db():
            async with Session() as db:
                yield db

        current_user_id = {"value": it_user_id}

        async def override_current_user():
            async with Session() as db:
                user = await db.get(User, current_user_id["value"])
                return user

        fastapi_app.dependency_overrides[get_db] = override_get_db
        fastapi_app.dependency_overrides[get_current_user] = (
            override_current_user
        )

        transport = ASGITransport(app=fastapi_app)

        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            # Проверяем ленту студента 2-го курса ИТ.
            response_it = await client.get("/api/v1/posts/feed")

            assert response_it.status_code == 200

            titles_it = {
                post["title"] for post in response_it.json()
            }

            assert "Грант на ИТ-стартап" in titles_it
            assert "Обходной лист выпускника" not in titles_it

            # Проверяем ленту студента 4-го курса экономики.
            current_user_id["value"] = graduate_user_id

            response_graduate = await client.get(
                "/api/v1/posts/feed"
            )

            assert response_graduate.status_code == 200

            titles_graduate = {
                post["title"] for post in response_graduate.json()
            }

            assert "Обходной лист выпускника" in titles_graduate
            assert "Грант на ИТ-стартап" not in titles_graduate

    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
