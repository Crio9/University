"""Complete API flow on SQLite and, when configured, isolated PostgreSQL schemas."""

import asyncio
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models import Category, Post, RawContent, StudentProfile, Tag, User
from app.models.student_interest import student_interests
from app.services import classification
from app.services.ai_classifier import MockAIProvider
from app.services.dictionaries import sync_reference_data
from app.services.processing import get_processing_session_factory
from tests.test_ai_classification import valid_result


@pytest.fixture(params=["sqlite", "postgres"])
async def flow_env(request, monkeypatch):
    schema = None
    admin = None
    if request.param == "postgres":
        url = os.environ.get("TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set TEST_DATABASE_URL for PostgreSQL integration tests")
        schema = "llm_test_" + uuid.uuid4().hex
        admin = create_async_engine(url)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_async_engine(
            url, connect_args={"server_settings": {"search_path": schema}}
        )
    else:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        monkeypatch.setattr(settings, "AI_PROCESSING_CONCURRENCY", 1)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            await sync_reference_data(db)
            staff = User(
                email="flow-staff@example.test",
                password_hash="unused",
                full_name="Staff",
                role="staff",
            )
            db.add(staff)
            users = {}
            career_id = await db.scalar(select(Tag.id).where(Tag.code == "CAREER"))
            for name, faculty, course, group, program in [
                ("iot3", "ИОТ", 3, "ИВТ-31", "ПМИ"),
                ("iot4", "ИОТ", 4, "ИВТ-41", "ПМИ"),
                ("iot2", "ИОТ", 2, "ИВТ-21", "ПМИ"),
                ("fit3", "ФИТ", 3, "ФИТ-31", "ИС"),
                ("law3", "Юрфак", 3, "ЮР-31", "Право"),
                ("no_interest", "ИОТ", 3, "ИВТ-32", "ПМИ"),
                ("alias3", "иот", 3, "ИВТ-33", "ПМИ"),
            ]:
                user = User(
                    email=f"{name}@example.test",
                    password_hash="unused",
                    full_name=name,
                    role="student",
                )
                db.add(user)
                await db.flush()
                db.add(
                    StudentProfile(
                        user_id=user.id,
                        faculty=faculty,
                        course=course,
                        study_group=group,
                        study_program=program,
                    )
                )
                await db.flush()
                if name != "no_interest":
                    await db.execute(
                        student_interests.insert().values(
                            student_id=user.id, tag_id=career_id
                        )
                    )
                users[name] = user.id
            await db.commit()
            staff_id = staff.id

        async def get_review_db():
            async with Session() as db:
                yield db

        app.dependency_overrides[get_db] = get_review_db
        app.dependency_overrides[get_processing_session_factory] = lambda: Session
        provider = MockAIProvider(
            valid_result(
                target_audience={
                    "faculty": ["ИОТ", "ФИТ"],
                    "program": [],
                    "course": [3, 4],
                    "group": [],
                }
            )
        )
        # Exercise the real configuration -> RawContent adapter -> domain pipeline wiring.
        monkeypatch.setattr(settings, "NVIDIA_API_KEY", "test-only")
        monkeypatch.setattr(classification, "NVIDIAAIProvider", lambda: provider)
        headers = lambda user_id: {
            "Authorization": "Bearer " + create_access_token(str(user_id))
        }
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield {
                "client": client,
                "Session": Session,
                "provider": provider,
                "staff": headers(staff_id),
                "users": {name: headers(user_id) for name, user_id in users.items()},
                "backend": request.param,
            }
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()


@pytest.mark.asyncio
async def test_telegram_ai_feed_save_flow(flow_env):
    env = flow_env
    client = env["client"]
    payload = {
        "channel": "dstu_live",
        "messages": [
            {
                "message_id": 10001,
                "text": "Стажировка для ИОТ и ФИТ 3–4 курса до 15 ноября.",
            }
        ],
    }
    first = await client.post(
        "/api/v1/ingest/import", headers=env["staff"], json=payload
    )
    assert first.status_code == 200 and first.json()["inserted"] == 1
    async with env["Session"]() as db:
        raw = (await db.scalars(select(RawContent))).one()
        post = (await db.scalars(select(Post))).one()
        post_id, raw_id = post.id, raw.id
        assert raw.status == "processed"
        assert raw.ai_result["confidence"] == 0.93
        assert post.raw_content_id == raw_id
        assert post.summary == env["provider"].result["summary"]
        assert post.ai_confidence == 0.93
        assert post.target_audience["faculty"] == ["ИОТ", "ФИТ"]
        assert post.target_audience["course"] == [3, 4]
        assert post.target_faculty is None and post.target_course is None
        assert (await db.get(Category, post.category_id)).code == "OPPORTUNITY"
        assert {t.code for t in post.tags} == {"CAREER", "INTERNSHIP"}
    for name in env["users"]:
        response = await client.get("/api/v1/posts/feed", headers=env["users"][name])
        assert response.status_code == 200
        assert (post_id in {p["id"] for p in response.json()}) == (
            name in {"iot3", "iot4", "fit3", "alias3"}
        )
    saved = await client.post(
        f"/api/v1/posts/{post_id}/save", headers=env["users"]["iot3"]
    )
    assert saved.status_code == 200 and saved.json()["is_saved"] is True
    assert saved.json()["target_audience"]["course"] == [3, 4]
    listing = await client.get("/api/v1/posts/saved", headers=env["users"]["iot3"])
    assert [p["id"] for p in listing.json()] == [post_id]
    assert listing.json()[0]["is_saved"] is True
    second = await client.post(
        "/api/v1/ingest/import", headers=env["staff"], json=payload
    )
    assert second.json()["inserted"] == 0 and second.json()["duplicates"] == 1
    retry = await client.post(
        f"/api/v1/ingest/raw/{raw_id}/retry", headers=env["staff"]
    )
    assert retry.status_code == 200 and retry.json()["status"] == "processed"
    assert env["provider"].calls == 1


@pytest.mark.asyncio
async def test_group_targeting_is_enforced(flow_env):
    env = flow_env
    env["provider"].result = valid_result(
        category="ACADEMIC",
        tags=["EXAM"],
        target_audience={
            "faculty": [],
            "program": [],
            "course": [],
            "group": ["ИВТ-31", "ИВТ-41"],
        },
    )
    r = await env["client"].post(
        "/api/v1/ingest/import",
        headers=env["staff"],
        json={
            "channel": "dstu_live",
            "messages": [
                {"message_id": 20002, "text": "Перенос экзамена для ИВТ-31 и ИВТ-41."}
            ],
        },
    )
    assert r.status_code == 200
    for name in env["users"]:
        feed = await env["client"].get("/api/v1/posts/feed", headers=env["users"][name])
        assert bool(feed.json()) == (name in {"iot3", "iot4"})


@pytest.mark.asyncio
async def test_existing_pending_queue_can_be_processed(flow_env):
    env = flow_env
    async with env["Session"]() as db:
        raw = RawContent(source_type="manual", raw_text="Queued before configuration")
        db.add(raw)
        await db.commit()
        raw_id = raw.id
    r = await env["client"].post("/api/v1/ingest/process-pending", headers=env["staff"])
    assert r.status_code == 200 and r.json()["queued"] == 1
    async with env["Session"]() as db:
        assert (await db.get(RawContent, raw_id)).status == "processed"


@pytest.mark.asyncio
async def test_manual_edit_preserves_group_restrictions(flow_env):
    env = flow_env
    category_id = None
    async with env["Session"]() as db:
        category_id = await db.scalar(
            select(Category.id).where(Category.code == "ACADEMIC")
        )
    audience = {"faculty": [], "program": [], "course": [3, 4], "group": ["ИВТ-31"]}
    created = await env["client"].post(
        "/api/v1/posts",
        headers=env["staff"],
        json={
            "title": "Manual",
            "content": "Text",
            "category_id": category_id,
            "target_audience": audience,
        },
    )
    assert created.status_code == 201
    post_id = created.json()["id"]
    changed = await env["client"].put(
        f"/api/v1/posts/{post_id}", headers=env["staff"], json={"target_course": 3}
    )
    assert changed.status_code == 200
    assert changed.json()["target_audience"] == dict(audience, course=[3])
    assert changed.json()["target_course"] == 3
    for name in ["iot3", "iot4", "alias3"]:
        feed = await env["client"].get("/api/v1/posts/feed", headers=env["users"][name])
        assert bool(feed.json()) == (name == "iot3")


@pytest.mark.asyncio
async def test_invalid_background_result_remains_in_raw_queue(flow_env):
    env = flow_env
    env["provider"].result = valid_result(summary=123)
    r = await env["client"].post(
        "/api/v1/ingest/import",
        headers=env["staff"],
        json={
            "channel": "dstu_live",
            "messages": [{"message_id": 30003, "text": "Invalid response"}],
        },
    )
    assert r.status_code == 200 and r.json()["inserted"] == 1
    raw = await env["client"].get(
        "/api/v1/ingest/raw?status=failed", headers=env["staff"]
    )
    assert len(raw.json()) == 1 and raw.json()[0]["processing_error"]
    async with env["Session"]() as db:
        assert await db.scalar(select(func.count()).select_from(Post)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("flow_env", ["postgres"], indirect=True)
async def test_concurrent_processing_creates_one_post(flow_env):
    env = flow_env
    async with env["Session"]() as db:
        raw = RawContent(source_type="manual", raw_text="Concurrent processing")
        db.add(raw)
        await db.commit()
        raw_id = raw.id

    async def run():
        async with env["Session"]() as db:
            raw = await db.get(RawContent, raw_id)
            await classification.process_raw_content(db, raw)
            await db.commit()

    await asyncio.gather(*(run() for _ in range(8)))
    assert env["provider"].calls == 1
    async with env["Session"]() as db:
        assert await db.scalar(select(func.count()).select_from(Post)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("flow_env", ["postgres"], indirect=True)
async def test_concurrent_manual_imports_share_one_classification(flow_env):
    env = flow_env
    body = {
        "source_type": "manual",
        "external_id": "concurrent",
        "raw_text": "Concurrent imports",
    }

    async def run():
        return await env["client"].post(
            "/api/v1/ingest/raw", headers=env["staff"], json=body
        )

    responses = await asyncio.gather(*(run() for _ in range(8)))
    assert all(r.status_code == 201 for r in responses)
    assert len({r.json()["id"] for r in responses}) == 1
    assert env["provider"].calls == 1
    async with env["Session"]() as db:
        assert await db.scalar(select(func.count()).select_from(RawContent)) == 1
        assert await db.scalar(select(func.count()).select_from(Post)) == 1
