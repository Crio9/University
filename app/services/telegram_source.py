"""Read text posts from Telegram public channel previews (no credentials)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

_USERNAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}\Z")
_POST_ID = re.compile(r"([A-Za-z][A-Za-z0-9_]{4,31})/([1-9][0-9]*)\Z")


class TelegramFetchError(RuntimeError):
    """Cannot retrieve or interpret the public channel preview."""


def clean_channel(value: str) -> str:
    """Reject paths/URLs; the only network target is t.me/s/<username>."""
    username = value.strip()
    if username.startswith("@"):
        username = username[1:]
    if not _USERNAME.fullmatch(username):
        raise ValueError("Use a public Telegram username (5–32 letters/digits/_)")
    return username.lower()


@dataclass(frozen=True)
class TelegramMessage:
    channel: str
    message_id: int
    text: str
    published_at: datetime | None = None

    @property
    def external_id(self) -> str:
        return f"{self.channel}:{self.message_id}"

    @property
    def source_url(self) -> str:
        return f"https://t.me/{self.channel}/{self.message_id}"


def parse_telegram_html(
    html: str, *, channel: str, limit: int = 20
) -> list[TelegramMessage]:
    """Parse visible text messages from the latest public preview page."""
    username = clean_channel(channel)
    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.select(".tgme_widget_message[data-post]")
    if not nodes:
        raise TelegramFetchError("No post markup found: private/blocked channel or HTML changed")

    unique: dict[int, TelegramMessage] = {}
    for node in nodes:
        match = _POST_ID.fullmatch(node.get("data-post", ""))
        if match is None or match.group(1).lower() != username:
            continue

        text_node = node.select_one(".tgme_widget_message_text")
        if text_node is None:
            text_node = node.select_one(".tgme_widget_message_caption")
        if text_node is None:
            continue  # media-only posts do not have a RawContent.raw_text
        body = text_node.get_text(separator="\n", strip=True).strip()
        if not body:
            continue

        published_at = None
        time_node = node.select_one("time[datetime]")
        if time_node is not None:
            try:
                published_at = datetime.fromisoformat(
                    time_node.get("datetime", "").replace("Z", "+00:00")
                )
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        message_id = int(match.group(2))
        unique[message_id] = TelegramMessage(username, message_id, body, published_at)

    return [unique[message_id] for message_id in sorted(unique)[-limit:]]


def fetch_channel_messages(channel: str, limit: int = 20) -> list[TelegramMessage]:
    """Fetch a single recent-messages page. This does not read full history."""
    username = clean_channel(channel)
    try:
        response = httpx.get(
            f"https://t.me/s/{username}",
            timeout=httpx.Timeout(15.0, connect=5.0),
            follow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; UniversityIngestion/1.0)"},
        )
        if response.is_redirect:
            raise TelegramFetchError("Telegram preview redirected; refusing redirect")
        response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise TelegramFetchError(f"Failed to fetch @{username}: {exc}") from exc
    return parse_telegram_html(response.text, channel=username, limit=limit)
