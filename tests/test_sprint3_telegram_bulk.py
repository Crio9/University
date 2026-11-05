"""Regression tests for HTML preview pagination and bulk ingestion."""
import pytest
from sqlalchemy import select, func

from app.services import telegram_source
from app.services.telegram_source import TelegramMessage, fetch_channel_messages
from app.schemas.telegram_ingest import TelegramImportRequest, TelegramSyncRequest
from app.models.raw_content import RawContent
from tests.test_ingest import env  # noqa: F401


def test_large_limits_are_validated():
    assert TelegramSyncRequest(channel="dstu_live", limit=300).limit == 300
    assert len(TelegramImportRequest(channel="dstu_live", messages=[{"message_id": i, "text": "hello"} for i in range(1, 1001)]).messages) == 1000
    with pytest.raises(Exception):
        TelegramSyncRequest(channel="dstu_live", limit=301)


@pytest.mark.asyncio
async def test_fetch_paginates_by_before(monkeypatch):
    history = [
        [40, 41, 42], [37, 38, 39], [34, 35, 36]
    ]

    class Response:
        is_redirect = False
        def __init__(self, html):
            self.text = html
        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            self.calls = 0
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, url, **kwargs):
            assert url == "https://t.me/s/dstu_live"
            assert kwargs.get("params", {}).get("before") == [None, 40, 37][self.calls]
            page = history[self.calls]
            self.calls += 1
            html = "".join(f'<div class="tgme_widget_message" data-post="dstu_live/{x}"><div class="tgme_widget_message_text">post {x}</div></div>' for x in page)
            return Response(html)

    monkeypatch.setattr(telegram_source.httpx, "AsyncClient", FakeClient)
    posts = await fetch_channel_messages("dstu_live", limit=7)
    assert [p.message_id for p in posts] == [36, 37, 38, 39, 40, 41, 42]


@pytest.mark.asyncio
async def test_bulk_import_deduplicates_and_keeps_first_payload(env):
    client = env["client"]
    raw = [{"message_id": i, "text": f"post-{i}"} for i in range(1, 202)]
    raw.append({"message_id": 1, "text": "duplicate must be ignored"})
    body = {"channel": "dstu_live", "messages": raw}
    first = await client.post("/api/v1/ingest/import", json=body, headers=env["staff"])
    assert first.status_code == 200, first.text
    assert first.json()["inserted"] == 201
    assert first.json()["duplicates"] == 1
    second = await client.post("/api/v1/ingest/import", json=body, headers=env["staff"])
    assert second.status_code == 200, second.text
    assert second.json()["inserted"] == 0
    async with env["Session"]() as db:
        assert await db.scalar(select(func.count()).select_from(RawContent)) == 201
        first_row = await db.scalar(select(RawContent).where(RawContent.external_id == "dstu_live:1"))
        assert first_row.raw_text == "post-1"
