"""Integration tests using the project's existing PostgreSQL-backed fixtures."""

from app.models.raw_content import RawContent, RawContentStatus
from app.services.telegram_source import TelegramMessage


def _staff_headers(client):
    created = client.post("/api/v1/auth/register", json={
        "email": "staff-telegram@example.com", "password": "staff123",
        "role": "staff", "full_name": "Staff", "department": "IT"
    })
    assert created.status_code == 201, created.text
    response = client.post("/api/v1/auth/login", data={
        "username": "staff-telegram@example.com", "password": "staff123"
    })
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_sync_is_idempotent(client, db, monkeypatch):
    headers = _staff_headers(client)
    sample = [TelegramMessage("dstu_live", 24, "Стажировка")]
    monkeypatch.setattr("app.api.telegram_ingest.fetch_channel_messages", lambda channel, limit: sample)
    path = "/api/v1/ingest/sync"
    assert client.post(path, json={"channel": "dstu_live"}).status_code == 401
    first = client.post(path, json={"channel": "dstu_live"}, headers=headers)
    second = client.post(path, json={"channel": "dstu_live"}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["inserted"] == 1
    assert first.json()["duplicates"] == 0
    assert second.json()["inserted"] == 0
    assert second.json()["duplicates"] == 1
    rows = db.query(RawContent).all()
    assert len(rows) == 1
    assert rows[0].external_id == "dstu_live:24"
    assert rows[0].status == RawContentStatus.PENDING
    assert rows[0].raw_text == "Стажировка"


def test_json_import_keeps_original_message(client, db):
    headers = _staff_headers(client)
    payload = {"channel": "dstu_live", "messages": [
        {"message_id": 42, "text": "Первый текст", "published_at": "2026-10-23T09:00:00+03:00"},
        {"message_id": 42, "text": "Подмена текста"},
    ]}
    response = client.post("/api/v1/ingest/import", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["inserted"] == 1
    assert response.json()["duplicates"] == 1
    raw = db.query(RawContent).one()
    assert raw.raw_text == "Первый текст"
    assert raw.source_type == "telegram"
    assert raw.ingest_metadata == {"channel": "dstu_live", "message_id": 42}
