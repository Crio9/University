"""Telegram HTML parser unit tests; no external network is needed."""
from datetime import datetime, timezone

import pytest

from app.services.telegram_source import (
    TelegramFetchError,
    clean_channel,
    parse_telegram_html,
)

HTML = """
<div class="tgme_widget_message" data-post="dstu_live/100">
  <div class="tgme_widget_message_text">ДГТУ <b>стажировка</b><br>до 15 ноября</div>
  <time datetime="2026-10-21T12:00:00+00:00"></time>
  <span>views 42</span>
</div>
<div class="tgme_widget_message" data-post="dstu_live/101">
  <div class="tgme_widget_message_text">Второй текст</div>
  <time datetime="2026-10-22T11:30:00Z"></time>
</div>
<div class="tgme_widget_message" data-post="other_chan/999">
  <div class="tgme_widget_message_text">Чужой пост</div>
</div>
"""


def test_parse_text_dates_and_limit():
    messages = parse_telegram_html(HTML, channel="@DSTU_LIVE")
    assert [message.external_id for message in messages] == [
        "dstu_live:100",
        "dstu_live:101",
    ]
    assert messages[0].source_url == "https://t.me/dstu_live/100"
    assert "стажировка" in messages[0].text
    assert "views 42" not in messages[0].text
    assert messages[1].published_at == datetime(
        2026, 10, 22, 11, 30, tzinfo=timezone.utc
    )
    assert [m.message_id for m in parse_telegram_html(
        HTML, channel="dstu_live", limit=1
    )] == [101]


@pytest.mark.parametrize("value", [
    "http://127.0.0.1/", "https://t.me/s/dstu_live", "../../local",
    "dstu_live?before=1", "a", "@@dstu_live",
])
def test_reject_unsafe_channel(value):
    with pytest.raises(ValueError):
        clean_channel(value)


def test_reject_unavailable_preview():
    with pytest.raises(TelegramFetchError):
        parse_telegram_html("<html>No public preview</html>", channel="dstu_live")


def test_media_only_is_skipped():
    html = '<div class="tgme_widget_message" data-post="dstu_live/5"><a class="tgme_widget_message_photo_wrap"></a></div>'
    assert parse_telegram_html(html, channel="dstu_live") == []


@pytest.mark.asyncio
async def test_fetch_refuses_redirect(monkeypatch):
    from app.services import telegram_source

    class FakeResponse:
        is_redirect = True

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, **kwargs):
            assert url == "https://t.me/s/dstu_live"
            return FakeResponse()

    monkeypatch.setattr(telegram_source.httpx, "AsyncClient", FakeClient)
    with pytest.raises(TelegramFetchError, match="redirected"):
        await telegram_source.fetch_channel_messages("dstu_live")
