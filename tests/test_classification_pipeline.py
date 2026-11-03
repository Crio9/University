import pytest
from sqlalchemy import func, select

from app.models import Category, Post, RawContent, Tag
from app.services import classification
from tests.test_ai_classification import valid_result
from tests.test_ingest import env, _FakeClassifier  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected_status",
    [
        (valid_result(tags=["UNKNOWN_TAG"]), "needs_review"),
        (
            valid_result(
                target_audience={
                    "faculty": ["Несуществующий факультет"],
                    "program": [],
                    "course": [3],
                    "group": [],
                }
            ),
            "needs_review",
        ),
        (
            valid_result(
                target_audience={
                    "faculty": [],
                    "program": [],
                    "course": [],
                    "group": ["НЕИЗВЕСТНАЯ-31"],
                }
            ),
            "needs_review",
        ),
        (valid_result(summary=123), "failed"),
    ],
)
async def test_unsafe_classification_does_not_create_post(
    env, monkeypatch, payload, expected_status
):
    monkeypatch.setattr(
        classification, "get_classifier", lambda: _FakeClassifier(payload)
    )
    r = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["staff"],
        json={"source_type": "manual", "raw_text": "Проверка"},
    )
    assert r.status_code == 201
    assert r.json()["status"] == expected_status
    assert r.json()["processing_error"]
    async with env["Session"]() as db:
        assert (await db.scalar(select(func.count()).select_from(Post))) == 0
        assert (await db.scalar(select(func.count()).select_from(Category))) == 5
        assert (await db.scalar(select(func.count()).select_from(Tag))) == 25


@pytest.mark.asyncio
async def test_retries_preserve_one_post_and_all_metadata(env, monkeypatch):
    payload = valid_result(
        target_audience={
            "faculty": ["фист"],
            "program": ["ПМИ"],
            "course": [2, 3],
            "group": ["ФИСТ-21"],
        }
    )
    calls = []

    class Provider:
        async def classify(self, raw):
            calls.append(raw.id)
            return payload

    monkeypatch.setattr(classification, "get_classifier", lambda: Provider())
    body = {"source_type": "manual", "external_id": "same", "raw_text": "Стажировка"}
    first = await env["client"].post(
        "/api/v1/ingest/raw", headers=env["staff"], json=body
    )
    raw_id = first.json()["id"]
    assert first.json()["status"] == "processed"
    for _ in range(2):
        r = await env["client"].post(
            f"/api/v1/ingest/raw/{raw_id}/retry", headers=env["staff"]
        )
        assert r.status_code == 200 and r.json()["status"] == "processed"
    again = await env["client"].post(
        "/api/v1/ingest/raw", headers=env["staff"], json=body
    )
    assert again.status_code == 201 and again.json()["id"] == raw_id
    assert calls == [raw_id]
    async with env["Session"]() as db:
        post = (await db.scalars(select(Post))).one()
        assert post.summary == payload["summary"]
        assert post.ai_confidence == payload["confidence"]
        assert post.raw_content_id == raw_id
        assert post.target_audience == {
            "faculty": ["ФИТ"],
            "program": ["ПМИ"],
            "course": [2, 3],
            "group": ["ФИСТ-21"],
        }
        assert post.target_course is None
        assert {tag.code for tag in post.tags} == {"CAREER", "INTERNSHIP"}
        assert (await db.get(Category, post.category_id)).code == "OPPORTUNITY"


@pytest.mark.asyncio
async def test_provider_failure_is_saved_and_retry_recovers(env, monkeypatch):
    class Broken:
        async def classify(self, raw):
            raise TimeoutError("Provider unavailable")

    monkeypatch.setattr(classification, "get_classifier", lambda: Broken())
    r = await env["client"].post(
        "/api/v1/ingest/raw",
        headers=env["staff"],
        json={"source_type": "manual", "raw_text": "Text"},
    )
    assert r.json()["status"] == "failed"
    payload = valid_result(
        target_audience={"faculty": [], "program": [], "course": [], "group": []}
    )
    monkeypatch.setattr(
        classification, "get_classifier", lambda: _FakeClassifier(payload)
    )
    retry = await env["client"].post(
        f"/api/v1/ingest/raw/{r.json()['id']}/retry", headers=env["staff"]
    )
    assert retry.json()["status"] == "processed"
    assert retry.json()["processing_error"] is None
