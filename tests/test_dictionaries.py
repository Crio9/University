import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.database import get_db
from app.main import app as fastapi_app
from app.models.dictionaries import Category, Tag
from app.models.user import User


@pytest.mark.asyncio
async def test_dictionaries_and_post_tags():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as session:
            cat = Category(name="Возможности")
            tag1 = Tag(name="ИТ")
            tag2 = Tag(name="Карьера")
            admin = User(
                email="admin@uni.test",
                password_hash=hash_password("adminpass"),
                full_name="Admin",
                role="admin",
            )
            session.add_all([cat, tag1, tag2, admin])
            await session.commit()
            cat_id = cat.id
            tag1_id = tag1.id
            tag2_id = tag2.id
            admin_id = admin.id

        async def override_get_db():
            async with Session() as session:
                yield session

        fastapi_app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=fastapi_app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            tags_res = await client.get("/api/v1/tags")
            assert tags_res.status_code == 200
            assert len(tags_res.json()) == 2

            cats_res = await client.get("/api/v1/categories")
            assert cats_res.status_code == 200
            assert len(cats_res.json()) == 1

            token = create_access_token(str(admin_id))
            headers = {"Authorization": f"Bearer {token}"}
            post_res = await client.post(
                "/api/v1/posts",
                headers=headers,
                json={
                    "title": "Новый пост с тегами",
                    "content": "Текст поста",
                    "category_id": cat_id,
                    "importance": "high",
                    "tag_ids": [tag1_id, tag2_id],
                },
            )
            assert post_res.status_code == 201
            data = post_res.json()
            assert len(data["tags"]) == 2
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()


@pytest.mark.asyncio
async def test_post_validation_rejects_unknown_and_invalid_values():
    """B-03: client errors must be 4xx, never 500 or silently ignored."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as session:
            admin = User(
                email="admin2@uni.test",
                password_hash=hash_password("adminpass"),
                full_name="Admin",
                role="admin",
            )
            session.add(admin)
            await session.commit()
            admin_id = admin.id

        async def override_get_db():
            async with Session() as session:
                yield session

        fastapi_app.dependency_overrides[get_db] = override_get_db
        headers = {"Authorization": f"Bearer {create_access_token(str(admin_id))}"}
        transport = ASGITransport(app=fastapi_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            unknown_category = await client.post(
                "/api/v1/posts",
                headers=headers,
                json={"title": "T", "content": "C", "category_id": 999999},
            )
            assert unknown_category.status_code == 400

            unknown_tags = await client.post(
                "/api/v1/posts",
                headers=headers,
                json={"title": "T", "content": "C", "category_id": 1, "tag_ids": [999999]},
            )
            assert unknown_tags.status_code == 400

            too_long = await client.post(
                "/api/v1/posts",
                headers=headers,
                json={"title": "x" * 300, "content": "C", "category_id": 1},
            )
            assert too_long.status_code == 422

            bad_course = await client.post(
                "/api/v1/posts",
                headers=headers,
                json={
                    "title": "T",
                    "content": "C",
                    "category_id": 1,
                    "target_course": 9,
                },
            )
            assert bad_course.status_code == 422

            duplicate_tags = await client.post(
                "/api/v1/posts",
                headers=headers,
                json={
                    "title": "T",
                    "content": "C",
                    "category_id": 1,
                    "tag_ids": [1, 1],
                },
            )
            assert duplicate_tags.status_code in (400, 422)
    finally:
        fastapi_app.dependency_overrides.clear()
        await engine.dispose()
