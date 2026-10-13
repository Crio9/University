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
