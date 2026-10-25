import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.database import get_db
from app.main import app as fastapi_app
from app.models.dictionaries import Category
from app.models.post import Post
from app.models.saved_post import UserSavedPost
from app.models.user import User


@pytest.fixture
async def env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as session:
        staff = User(
            email="staff@uni.test",
            password_hash=hash_password("pass123"),
            full_name="Staff",
            role="staff",
        )
        student = User(
            email="student@uni.test",
            password_hash=hash_password("pass123"),
            full_name="Student",
            role="student",
        )
        category = Category(name="Новости", code="NEWS")
        session.add_all([staff, student, category])
        await session.flush()

        post = Post(
            title="Для всех студентов",
            content="Общая новость",
            category_id=category.id,
            author_id=staff.id,
            importance="standard",
        )
        session.add(post)
        await session.commit()
        staff_id, student_id, post_id = staff.id, student.id, post.id

    async def override_get_db():
        async with Session() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "Session": Session,
            "staff": {"Authorization": f"Bearer {create_access_token(str(staff_id))}"},
            "student": {"Authorization": f"Bearer {create_access_token(str(student_id))}"},
            "post_id": post_id,
        }

    fastapi_app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_save_and_unsave_flow(env):
    client, student, post_id = env["client"], env["student"], env["post_id"]

    saved = await client.post(f"/api/v1/posts/{post_id}/save", headers=student)
    assert saved.status_code == 200
    assert saved.json()["is_saved"] is True

    listing = await client.get("/api/v1/posts/saved", headers=student)
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [post_id]
    assert listing.json()[0]["is_saved"] is True

    removed = await client.delete(f"/api/v1/posts/{post_id}/save", headers=student)
    assert removed.status_code == 200
    assert removed.json()["is_saved"] is False

    assert (await client.get("/api/v1/posts/saved", headers=student)).json() == []


@pytest.mark.asyncio
async def test_save_is_idempotent(env):
    client, student, post_id = env["client"], env["student"], env["post_id"]
    assert (await client.post(f"/api/v1/posts/{post_id}/save", headers=student)).status_code == 200
    assert (await client.post(f"/api/v1/posts/{post_id}/save", headers=student)).status_code == 200

    async with env["Session"]() as session:
        result = await session.execute(select(UserSavedPost))
        assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_unsave_is_idempotent(env):
    client, student, post_id = env["client"], env["student"], env["post_id"]
    response = await client.delete(f"/api/v1/posts/{post_id}/save", headers=student)
    assert response.status_code == 200
    assert response.json()["is_saved"] is False


@pytest.mark.asyncio
async def test_feed_exposes_is_saved_flag(env):
    client, student, post_id = env["client"], env["student"], env["post_id"]
    # The seed helper creates a student without a profile; give it the matching
    # context so the smart feed returns the post.
    async with env["Session"]() as session:
        from app.models.profile import StudentProfile

        session.add(StudentProfile(user_id=env_student_id(env)))
        await session.commit()

    await client.post(f"/api/v1/posts/{post_id}/save", headers=student)
    feed = await client.get("/api/v1/posts/feed", headers=student)
    assert feed.status_code == 200
    assert feed.json()[0]["is_saved"] is True


def env_student_id(env) -> int:
    token = env["student"]["Authorization"].split()[1]
    from app.core.security import decode_token

    return int(decode_token(token)["sub"])


@pytest.mark.asyncio
async def test_save_requires_authentication(env):
    response = await env["client"].post(f"/api/v1/posts/{env['post_id']}/save")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_unknown_post_returns_404(env):
    response = await env["client"].post(
        "/api/v1/posts/999999/save", headers=env["student"]
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_detail_exposes_is_saved(env):
    client, student, post_id = env["client"], env["student"], env["post_id"]
    detail = await client.get(f"/api/v1/posts/{post_id}", headers=student)
    assert detail.status_code == 200
    assert detail.json()["is_saved"] is False

    await client.post(f"/api/v1/posts/{post_id}/save", headers=student)
    detail = await client.get(f"/api/v1/posts/{post_id}", headers=student)
    assert detail.json()["is_saved"] is True
