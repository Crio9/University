"""Async API integration tests reusing sprint2-fix's in-memory test database."""
import pytest
from sqlalchemy import select

from app.models.raw_content import RawContent
from app.services.telegram_source import TelegramFetchError, TelegramMessage
from tests.test_ingest import env  # noqa: F401 - pytest fixture


@pytest.mark.asyncio
async def test_sync_saves_pending_and_deduplicates(env, monkeypatch):
    async def fake_fetch(channel, limit):
        assert channel == "dstu_live"
        return [TelegramMessage("dstu_live", 24, "Стажировка")]

    monkeypatch.setattr("app.api.telegram_ingest.fetch_channel_messages", fake_fetch)
    path = "/api/v1/ingest/sync"
    payload = {"channel": "@DSTU_LIVE"}
    client = env["client"]
    assert (await client.post(path, json=payload)).status_code == 401
    assert (await client.post(path, json=payload, headers=env["student"])).status_code == 403

    first = await client.post(path, json=payload, headers=env["staff"])
    second = await client.post(path, json=payload, headers=env["staff"])
    assert first.status_code == second.status_code == 200
    assert first.json()["inserted"] == 1
    assert second.json()["inserted"] == 0
    assert second.json()["duplicates"] == 1

    async with env["Session"]() as session:
        rows = (await session.execute(select(RawContent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].external_id == "dstu_live:24"
        assert rows[0].status == "pending"
        assert rows[0].raw_text == "Стажировка"
        assert rows[0].id > 0  # develop uses integer IDs


@pytest.mark.asyncio
async def test_multiple_channels_one_sync(env, monkeypatch):
    async def fake_fetch(channel, limit):
        return [TelegramMessage(channel, 42, f"Post from {channel}")]

    monkeypatch.setattr("app.api.telegram_ingest.fetch_channel_messages", fake_fetch)
    response = await env["client"].post(
        "/api/v1/ingest/sync",
        headers=env["staff"],
        json={"channels": ["dstu_live", "@DSTU_LIVE", "example_channel"], "limit": 1},
    )
    assert response.status_code == 200, response.text
    assert response.json()["channels"] == ["dstu_live", "example_channel"]
    assert response.json()["received"] == response.json()["inserted"] == 2


@pytest.mark.asyncio
async def test_json_fallback_keeps_first_payload(env):
    payload = {
        "channel": "dstu_live",
        "messages": [
            {"message_id": 42, "text": "Первый текст"},
            {"message_id": 42, "text": "Не заменять"},
        ],
    }
    response = await env["client"].post(
        "/api/v1/ingest/import", headers=env["staff"], json=payload
    )
    assert response.status_code == 200, response.text
    assert response.json()["inserted"] == response.json()["duplicates"] == 1
    async with env["Session"]() as session:
        rows = (await session.execute(select(RawContent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].raw_text == "Первый текст"
        assert rows[0].ingest_metadata == {"channel": "dstu_live", "message_id": 42}


@pytest.mark.asyncio
async def test_invalid_channel_does_not_trigger_fetch(env):
    response = await env["client"].post(
        "/api/v1/ingest/sync",
        headers=env["staff"],
        json={"channel": "http://127.0.0.1/private"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unavailable_telegram_is_reported_as_502(env, monkeypatch):
    async def failed_fetch(channel, limit):
        raise TelegramFetchError("Preview unavailable")

    monkeypatch.setattr("app.api.telegram_ingest.fetch_channel_messages", failed_fetch)
    response = await env["client"].post(
        "/api/v1/ingest/sync",
        headers=env["staff"],
        json={"channel": "dstu_live"},
    )
    assert response.status_code == 502
    assert "Preview unavailable" in response.json()["detail"]
