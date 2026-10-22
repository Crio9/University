import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import Category, Post, Tag, User
from app.schemas.ai_classification import AIClassificationResult
from app.services.post_classification import create_post_from_classification


@pytest.mark.asyncio
async def test_create_post_from_ai_classification():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as db:
            author = User(
                email="ai-test@example.test",
                password_hash="test-hash",
                full_name="AI Test",
                role="admin",
            )
            db.add(author)
            await db.flush()

            classification = AIClassificationResult(
                category="ACADEMIC",
                tags=["расписание", "учёба"],
                importance="NORMAL",
                deadline=None,
                target_audience={
                    "faculty": ["ИОТ"],
                    "program": ["Информационные системы"],
                    "course": [1],
                    "group": ["ИСТ-11"],
                },
                summary="Объявление об учебном расписании",
                confidence=0.95,
            )

            post = await create_post_from_classification(
                db,
                title="Изменение расписания",
                content="Завтра занятия начнутся в 10:00.",
                author_id=author.id,
                classification=classification,
            )

            await db.commit()

            assert post.id is not None
            assert post.title == "Изменение расписания"
            assert post.importance == "standard"
            assert post.target_faculty == "ИОТ"
            assert post.target_program == "Информационные системы"
            assert post.target_course == 1
            assert {tag.name for tag in post.tags} == {
                "расписание",
                "учёба",
            }

            category = await db.get(Category, post.category_id)
            assert category.name == "ACADEMIC"

            tags_count = len(post.tags)
            assert tags_count == 2

    finally:
        await engine.dispose()