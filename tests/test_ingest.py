import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.database import get_db
from app.main import app as fastapi_app
from app.models.post import Post
from app.models.raw_content import RawContent, RawContentStatus
from app.models.user import User
from app.services import classification
from app.services.dictionaries import sync_reference_data
from app.services.processing import get_processing_session_factory
from app.models.profile import StudentProfile


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
            full_name="Staff Member",
            role="staff",
        )
        student = User(
            email="student@uni.test",
            password_hash=hash_password("pass123"),
            full_name="Student",
            role="student",
        )
        session.add_all([staff, student])
        await session.flush()
        session.add(
            StudentProfile(
                user_id=student.id,
                faculty="ФИСТ",
                course=2,
                study_program="ПМИ",
                study_group="ФИСТ-21",
            )
        )
        await sync_reference_data(session)
        await session.commit()
        staff_id, student_id = staff.id, student.id

    async def override_get_db():
        async with Session() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_processing_session_factory] = lambda: Session
    transport = ASGITransport(app=fastapi_app)

    staff_headers = {"Authorization": f"Bearer {create_access_token(str(staff_id))}"}
    student_headers = {
        "Authorization": f"Bearer {create_access_token(str(student_id))}"
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "client": client,
            "Session": Session,
            "staff": staff_headers,
            "student": student_headers,
        }

    fastapi_app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_manual_ingestion_creates_pending_raw(env):
    response = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["staff"],
        json={
            "source_type": "manual",
            "external_id": "msg-1",
            "raw_text": "Текст публикации",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["external_id"] == "msg-1"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_manual_ingestion_is_idempotent(env):
    payload = {
        "source_type": "telegram",
        "external_id": "post-42",
        "raw_text": "Один и тот же пост",
    }
    first = await env["client"].post(
        "/api/v1/ingest/raw", headers=env["staff"], json=payload
    )
    second = await env["client"].post(
        "/api/v1/ingest/raw", headers=env["staff"], json=payload
    )
    assert first.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    async with env["Session"]() as session:
        result = await session.execute(select(RawContent))
        assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_ingest_requires_staff_role(env):
    response = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["student"],
        json={"source_type": "manual", "raw_text": "Текст"},
    )
    assert response.status_code == 403

    listing = await env["client"].get("/api/v1/ingest/raw", headers=env["student"])
    assert listing.status_code == 403

    anonymous = await env["client"].get("/api/v1/ingest/raw")
    assert anonymous.status_code == 401


@pytest.mark.asyncio
async def test_list_raw_filters_by_status(env):
    async with env["Session"]() as session:
        session.add_all(
            [
                RawContent(source_type="manual", raw_text="Pending"),
                RawContent(
                    source_type="manual",
                    external_id="failed-1",
                    raw_text="Failed",
                    status=RawContentStatus.FAILED.value,
                ),
            ]
        )
        await session.commit()

    response = await env["client"].get(
        "/api/v1/ingest/raw?status=failed", headers=env["staff"]
    )
    assert response.status_code == 200
    assert [item["status"] for item in response.json()] == ["failed"]

    bad = await env["client"].get(
        "/api/v1/ingest/raw?status=nonsense", headers=env["staff"]
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_retry_unknown_raw_returns_404(env):
    response = await env["client"].post(
        "/api/v1/ingest/raw/999999/retry", headers=env["staff"]
    )
    assert response.status_code == 404


class _FakeClassifier:
    def __init__(self, payload):
        self._payload = payload

    async def classify(self, raw):
        return self._payload


@pytest.mark.asyncio
async def test_retry_without_classifier_keeps_pending(env):
    async with env["Session"]() as session:
        raw = RawContent(
            source_type="manual",
            raw_text="Стажировка",
            status=RawContentStatus.FAILED.value,
            processing_error="prior failure",
        )
        session.add(raw)
        await session.commit()
        raw_id = raw.id

    response = await env["client"].post(
        f"/api/v1/ingest/raw/{raw_id}/retry", headers=env["staff"]
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_pipeline_creates_post_on_valid_classification(env, monkeypatch):
    payload = {
        "category": "OPPORTUNITY",
        "tags": ["CAREER", "INTERNSHIP"],
        "importance": "NORMAL",
        "deadline": "2026-11-15T23:59:59",
        "target_audience": {
            "faculty": ["ФИСТ"],
            "program": [],
            "course": [2],
            "group": [],
        },
        "summary": "Стажировка для студентов ФИСТ.",
        "confidence": 0.92,
    }
    monkeypatch.setattr(
        classification, "get_classifier", lambda: _FakeClassifier(payload)
    )

    response = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["staff"],
        json={
            "source_type": "telegram",
            "external_id": "tg-1",
            "raw_text": "VK приглашает студентов на стажировку.",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "processed"

    async with env["Session"]() as session:
        result = await session.execute(
            select(Post).where(Post.raw_content_id == response.json()["id"])
        )
        post = result.scalar_one()
        assert post.summary == "Стажировка для студентов ФИСТ."
        assert abs(post.ai_confidence - 0.92) < 1e-9
        assert post.importance == "standard"
        assert post.target_faculty == "ФИСТ"
        assert post.target_course == 2
        assert {tag.code for tag in post.tags} == {"CAREER", "INTERNSHIP"}


@pytest.mark.asyncio
async def test_pipeline_preserves_multiple_courses(env, monkeypatch):
    payload = {
        "category": "OPPORTUNITY",
        "tags": ["CAREER"],
        "importance": "NORMAL",
        "summary": "Для 3–4 курса",
        "target_audience": {
            "faculty": [],
            "program": [],
            "course": [3, 4],
            "group": [],
        },
        "confidence": 0.8,
    }
    monkeypatch.setattr(
        classification, "get_classifier", lambda: _FakeClassifier(payload)
    )

    response = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["staff"],
        json={
            "source_type": "manual",
            "raw_text": "Для 3-4 курса",
            "external_id": "amb-1",
        },
    )
    assert response.json()["status"] == "processed"

    async with env["Session"]() as session:
        result = await session.execute(
            select(Post).where(Post.raw_content_id == response.json()["id"])
        )
        post = result.scalar_one()
        assert post.target_audience["course"] == [3, 4]
        assert post.target_course is None


@pytest.mark.asyncio
async def test_pipeline_marks_needs_review_on_unresolved_values(env, monkeypatch):
    payload = {
        "category": "NEWS",
        "tags": ["КВАНТОВАЯ ФИЗИКА"],
        "importance": "NORMAL",
        "summary": "Проверка",
        "target_audience": {"faculty": [], "program": [], "course": [], "group": []},
        "confidence": 0.5,
    }
    monkeypatch.setattr(
        classification, "get_classifier", lambda: _FakeClassifier(payload)
    )

    response = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["staff"],
        json={"source_type": "manual", "raw_text": "Непонятно", "external_id": "bad-1"},
    )
    assert response.json()["status"] == "needs_review"


@pytest.mark.asyncio
async def test_pipeline_marks_failed_on_invalid_payload(env, monkeypatch):
    monkeypatch.setattr(
        classification,
        "get_classifier",
        lambda: _FakeClassifier({"tags": ["CAREER"]}),
    )

    response = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["staff"],
        json={
            "source_type": "manual",
            "raw_text": "Без категории",
            "external_id": "bad-2",
        },
    )
    assert response.json()["status"] == "failed"
    assert response.json()["processing_error"]


def test_validate_payload_rejects_bad_input():
    with pytest.raises(ValueError):
        classification.validate_payload({"category": "NEWS", "confidence": 2.0})
    with pytest.raises(ValueError):
        classification.validate_payload({"category": "NEWS", "deadline": "not-a-date"})
    with pytest.raises(ValueError):
        classification.validate_payload({"category": "NEWS", "importance": "URGENT"})
