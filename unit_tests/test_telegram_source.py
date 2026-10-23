"""Network- and database-free checks of the Telegram HTML adapter."""

from datetime import datetime, timezone

import pytest

from app.services.telegram_source import (
    TelegramFetchError,
    clean_channel,
    parse_telegram_html,
)

HTML = '''<div class="tgme_widget_message" data-post="dstu_live/100">
  <div class="tgme_widget_message_text js-message_text">ДГТУ <b>стажировка</b><br>до 15 ноября</div>
  <time datetime="2026-10-21T12:00:00+00:00"></time>
  <span class="tgme_widget_message_views">42 views</span>
</div>
<div class="tgme_widget_message" data-post="dstu_live/101">
  <div class="tgme_widget_message_text">Второй текст</div>
  <time datetime="2026-10-22T11:30:00Z"></time>
</div>
<div class="tgme_widget_message" data-post="foreign/999">
  <div class="tgme_widget_message_text">Не наш канал</div>
</div>'''


def test_parse_message_text_identity_date_and_limit():
    result = parse_telegram_html(HTML, channel="@DSTU_LIVE")
    assert len(result) == 2
    assert result[0].external_id == "dstu_live:100"
    assert result[0].source_url == "https://t.me/dstu_live/100"
    assert "стажировка" in result[0].text
    assert "42 views" not in result[0].text
    assert result[1].published_at == datetime(2026, 10, 22, 11, 30, tzinfo=timezone.utc)
    assert [msg.message_id for msg in parse_telegram_html(HTML, channel="dstu_live", limit=1)] == [101]


@pytest.mark.parametrize("channel", ["http://127.0.0.1/admin", "../../secret", "@@dstu_live", "a", "dstu_live?before=1"])
def test_reject_bad_channel(channel):
    with pytest.raises(ValueError):
        clean_channel(channel)


def test_reject_non_post_html():
    with pytest.raises(TelegramFetchError):
        parse_telegram_html("<html>login page</html>", channel="dstu_live")


def test_media_only_post_is_skipped():
    html = '<div class="tgme_widget_message" data-post="dstu_live/222"><a class="tgme_widget_message_photo_wrap"></a></div>'
    assert parse_telegram_html(html, channel="dstu_live") == []


def test_fetch_rejects_redirect_without_following_it(monkeypatch):
    from app.services.telegram_source import fetch_channel_messages

    class RedirectResponse:
        is_redirect = True

    def fake_get(url, **kwargs):
        assert url == "https://t.me/s/dstu_live"
        assert kwargs["follow_redirects"] is False
        return RedirectResponse()

    monkeypatch.setattr("app.services.telegram_source.httpx.get", fake_get)
    with pytest.raises(TelegramFetchError, match="redirected"):
        fetch_channel_messages("dstu_live")
