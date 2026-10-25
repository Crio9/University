"""Fetch text posts from public Telegram channel previews (no credentials).

A preview contains only a limited recent window; this is not a full-history API.
The supplied channel is always a username, never an arbitrary URL.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

_USERNAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}\Z")
_POST_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]{4,31})/([1-9][0-9]*)\Z")


class TelegramFetchError(RuntimeError):
    """The public Telegram preview could not be read or parsed."""


def clean_channel(value: str) -> str:
    """Accept @username or username, but never paths, URLs, or query strings."""
    name = value.strip().removeprefix("@")
    if not _USERNAME_RE.fullmatch(name):
        raise ValueError("Expected a public Telegram username (5-32 letters/digits/_)")
    return name.lower()


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
    """Read the visible text/caption, source identity, and date from t.me/s."""
    username = clean_channel(channel)
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")

    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.select(".tgme_widget_message[data-post]")
    if not nodes:
        raise TelegramFetchError(
            "No Telegram post markup found (private, unavailable, or changed HTML)"
        )

    messages: dict[int, TelegramMessage] = {}
    for node in nodes:
        post_id = node.get("data-post", "")
        match = _POST_RE.fullmatch(post_id)
        if match is None or match.group(1).lower() != username:
            continue

        content = node.select_one(
            ".tgme_widget_message_text, .tgme_widget_message_caption"
        )
        if content is None:
            continue  # media-only messages have no text for RawContent.raw_text
        text = content.get_text(separator="\n", strip=True).strip()
        if not text:
            continue

        published_at = None
        date_node = node.select_one("time[datetime]")
        if date_node is not None:
            try:
                published_at = datetime.fromisoformat(
                    date_node["datetime"].replace("Z", "+00:00")
                )
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                pass

        message_id = int(match.group(2))
        messages[message_id] = TelegramMessage(
            channel=username,
            message_id=message_id,
            text=text,
            published_at=published_at,
        )

    return sorted(messages.values(), key=lambda message: message.message_id)[-limit:]


async def fetch_channel_messages(
    channel: str, limit: int = 20
) -> list[TelegramMessage]:
    """Fetch one recent preview page; refuse redirects to other destinations."""
    username = clean_channel(channel)
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
        ) as client:
            response = await client.get(
                f"https://t.me/s/{username}",
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; UniversityIngestion/1.0)"
                },
            )
            if response.is_redirect:
                raise TelegramFetchError(
                    f"Telegram preview for @{username} redirected"
                )
            response.raise_for_status()
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise TelegramFetchError(
            f"Could not fetch public preview for @{username}: {exc}"
        ) from exc

    return parse_telegram_html(response.text, channel=username, limit=limit)
