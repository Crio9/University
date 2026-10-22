
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models import Category, Post, User
from app.services.ai_classifier import MockAIProvider
from app.services.classification_pipeline import classify_and_create_post


@pytest.mark.asyncio
async def test_classification_pipeline_with_mock_provider():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as db:
            author = User(
                email="pipeline-test@example.test",
                password_hash="test-hash",
                full_name="Pipeline Test",
                role="admin",
            )
            db.add(author)
            await db.flush()

            post = await classify_and_create_post(
                db,
                MockAIProvider(),
                title="Объявление о занятиях",
                content="Завтра занятия начнутся в 10:00.",
                author_id=author.id,
            )

            await db.commit()

            assert post.id is not None
            assert post.title == "Объявление о занятиях"
            assert post.importance == "standard"
            assert post.category_id is not None
            assert len(post.tags) == 2

            saved_post = await db.get(Post, post.id)
            assert saved_post is not None

            category = await db.get(Category, post.category_id)
            assert category is not None
            assert category.name == "ACADEMIC"

    finally:
        await engine.dispose()
