import pytest

from app.models.raw_content import RawContent, RawContentStatus
from app.services import classification
from app.services.dictionaries import sync_reference_data


def _headers(client, email: str, password: str) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _staff_and_student_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "staff@example.com",
            "password": "staff123",
            "role": "staff",
            "full_name": "Staff",
            "department": "Dean",
        },
    )
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "fit@example.com",
            "password": "student123",
            "role": "student",
            "full_name": "FIT Student",
            "faculty": "ФИТ",
            "course": 3,
        },
    )
    return (
        _headers(client, "staff@example.com", "staff123"),
        _headers(client, "fit@example.com", "student123"),
    )


def _add_raw(db, **kwargs) -> RawContent:
    raw = RawContent(
        source_type=kwargs.pop("source_type", "manual"),
        raw_text=kwargs.pop("raw_text", "Текст"),
        **kwargs,
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)
    return raw


def test_list_raw_content_requires_staff(client, db):
    _staff_headers, student_headers = _staff_and_student_headers(client)
    assert client.get("/api/v1/ingest/raw", headers=student_headers).status_code == 403
    assert client.get("/api/v1/ingest/raw").status_code == 401


def test_list_raw_content_returns_statuses(client, db):
    staff_headers, _ = _staff_and_student_headers(client)
    _add_raw(db, raw_text="Первое", status=RawContentStatus.PENDING)
    _add_raw(
        db,
        external_id="ext-2",
        raw_text="Второе",
        status=RawContentStatus.FAILED,
        processing_error="boom",
    )

    response = client.get("/api/v1/ingest/raw", headers=staff_headers)
    assert response.status_code == 200
    items = response.json()
    assert {item["status"] for item in items} == {"pending", "failed"}


def test_list_raw_content_filter_by_status(client, db):
    staff_headers, _ = _staff_and_student_headers(client)
    _add_raw(db, raw_text="Pending")
    _add_raw(
        db,
        external_id="ext-9",
        raw_text="Failed",
        status=RawContentStatus.FAILED,
    )

    response = client.get("/api/v1/ingest/raw?status=failed", headers=staff_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["status"] == "failed"


def test_retry_unknown_raw_returns_404(client, db):
    staff_headers, _ = _staff_and_student_headers(client)
    missing = "00000000-0000-0000-0000-000000000000"
    response = client.post(f"/api/v1/ingest/raw/{missing}/retry", headers=staff_headers)
    assert response.status_code == 404


def test_retry_requires_staff(client, db):
    _staff_headers, student_headers = _staff_and_student_headers(client)
    raw = _add_raw(db, raw_text="Что-то")
    response = client.post(f"/api/v1/ingest/raw/{raw.id}/retry", headers=student_headers)
    assert response.status_code == 403


def test_retry_without_classifier_keeps_pending(client, db):
    """With no AI provider configured nothing is written to the structured store."""
    staff_headers, _ = _staff_and_student_headers(client)
    raw = _add_raw(
        db,
        raw_text="Стажировка",
        status=RawContentStatus.FAILED,
        processing_error="prior failure",
    )
    response = client.post(f"/api/v1/ingest/raw/{raw.id}/retry", headers=staff_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


class _FakeClassifier:
    def __init__(self, payload):
        self._payload = payload

    def classify(self, raw):
        return self._payload


def test_pipeline_creates_post_on_valid_classification(client, db, monkeypatch):
    _staff_headers, _student_headers = _staff_and_student_headers(client)
    sync_reference_data(db)
    db.commit()

    payload = {
        "category": "OPPORTUNITY",
        "tags": ["CAREER", "INTERNSHIP"],
        "importance": "NORMAL",
        "deadline": "2026-11-15T23:59:59",
        "target_faculty": ["ИОТ"],
        "target_course": [3, 4],
        "summary": "Стажировка для студентов ИОТ.",
        "confidence": 0.92,
    }
    monkeypatch.setattr(classification, "get_classifier", lambda: _FakeClassifier(payload))

    staff_headers, _ = _staff_and_student_headers(client)
    raw = _add_raw(db, raw_text="VK приглашает студентов на стажировку.")
    response = client.post(f"/api/v1/ingest/raw/{raw.id}/retry", headers=staff_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "processed"

    from app.models.post import Post

    post = db.query(Post).filter(Post.raw_content_id == raw.id).one()
    assert post.summary == "Стажировка для студентов ИОТ."
    assert abs(post.ai_confidence - 0.92) < 1e-9
    assert post.category.slug == "opportunity"
    assert {tag.slug for tag in post.tags} == {"career", "internship"}


def test_pipeline_marks_needs_review_on_unresolved_values(client, db, monkeypatch):
    _staff_headers, _student_headers = _staff_and_student_headers(client)
    sync_reference_data(db)
    db.commit()

    payload = {"category": "КВАНТОВАЯ ФИЗИКА", "tags": ["CAREER"], "confidence": 0.5}
    monkeypatch.setattr(classification, "get_classifier", lambda: _FakeClassifier(payload))

    staff_headers, _ = _staff_and_student_headers(client)
    raw = _add_raw(db, raw_text="Непонятная публикация")
    response = client.post(f"/api/v1/ingest/raw/{raw.id}/retry", headers=staff_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "needs_review"

    from app.models.post import Post

    assert db.query(Post).filter(Post.raw_content_id == raw.id).count() == 0


def test_pipeline_marks_failed_on_invalid_payload(client, db, monkeypatch):
    _staff_headers, _student_headers = _staff_and_student_headers(client)
    monkeypatch.setattr(
        classification, "get_classifier", lambda: _FakeClassifier({"tags": ["CAREER"]})
    )

    staff_headers, _ = _staff_and_student_headers(client)
    raw = _add_raw(db, raw_text="Без категории")
    response = client.post(f"/api/v1/ingest/raw/{raw.id}/retry", headers=staff_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["processing_error"]


def test_validate_payload_rejects_bad_confidence():
    with pytest.raises(ValueError):
        classification.validate_payload({"category": "NEWS", "confidence": 2.0})


def test_validate_payload_rejects_bad_deadline():
    with pytest.raises(ValueError):
        classification.validate_payload({"category": "NEWS", "deadline": "not-a-date"})


def test_manual_ingestion_creates_pending_raw(client, db):
    staff_headers, _ = _staff_and_student_headers(client)
    response = client.post(
        "/api/v1/ingest/raw",
        headers=staff_headers,
        json={
            "source_type": "manual",
            "external_id": "msg-1",
            "raw_text": "Текст публикации",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "manual"
    assert body["external_id"] == "msg-1"
    assert body["status"] == "pending"


def test_manual_ingestion_is_idempotent(client, db):
    staff_headers, _ = _staff_and_student_headers(client)
    payload = {
        "source_type": "telegram",
        "external_id": "post-42",
        "raw_text": "Один и тот же пост",
    }
    first = client.post("/api/v1/ingest/raw", headers=staff_headers, json=payload)
    second = client.post("/api/v1/ingest/raw", headers=staff_headers, json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert db.query(RawContent).count() == 1


def test_manual_ingestion_requires_staff(client, db):
    _staff_headers, student_headers = _staff_and_student_headers(client)
    response = client.post(
        "/api/v1/ingest/raw",
        headers=student_headers,
        json={"source_type": "manual", "raw_text": "Текст"},
    )
    assert response.status_code == 403
