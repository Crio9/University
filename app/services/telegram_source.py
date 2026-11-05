"""Fetch text posts from public Telegram preview HTML (no Telegram credentials).

A public preview may show only a rolling window. The '?before=' parameter
can request older visible messages, but this is NOT a full-history API.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

_USERNAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}\Z")
_POST_RE = re.compile(r"([A-Za-z][A-Za-z0-9_]{4,31})/([1-9][0-9]*)\Z")
MAX_SYNC_LIMIT = 300
MAX_PAGES = 15


class TelegramFetchError(RuntimeError):
    """Could not read a public Telegram preview."""


def clean_channel(value: str) -> str:
    """Accept @username or username only, never arbitrary URLs/paths."""
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


def parse_telegram_html(html: str, *, channel: str, limit: int = 20) -> list[TelegramMessage]:
    """Read visible message text/caption, identity and timestamp."""
    username = clean_channel(channel)
    if not 1 <= limit <= MAX_SYNC_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_SYNC_LIMIT}")

    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.select(".tgme_widget_message[data-post]")
    if not nodes:
        raise TelegramFetchError("No Telegram post markup found (private, unavailable, or changed HTML)")

    messages: dict[int, TelegramMessage] = {}
    for node in nodes:
        post_id = node.get("data-post", "")
        match = _POST_RE.fullmatch(post_id)
        if match is None or match.group(1).lower() != username:
            continue
        content = node.select_one(".tgme_widget_message_text, .tgme_widget_message_caption")
        if content is None:
            continue
        text = content.get_text(separator="\n", strip=True).strip()
        if not text:
            continue
        published_at = None
        date_node = node.select_one("time[datetime]")
        if date_node is not None:
            try:
                published_at = datetime.fromisoformat(date_node["datetime"].replace("Z", "+00:00"))
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)
            except (ValueError, KeyError):
                pass
        message_id = int(match.group(2))
        messages[message_id] = TelegramMessage(username, message_id, text, published_at)
    return sorted(messages.values(), key=lambda item: item.message_id)[-limit:]


async def fetch_channel_messages(channel: str, limit: int = 20) -> list[TelegramMessage]:
    """Request several historical preview pages with bounded network traffic.

    Stops if older pages do not advance, are blocked, or have no text posts.
    Preview pages without message markup on the first page are errors.
    """
    username = clean_channel(channel)
    if not 1 <= limit <= MAX_SYNC_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_SYNC_LIMIT}")
    messages: dict[int, TelegramMessage] = {}
    oldest_id: int | None = None
    try:
        async with httpx.AsyncClient(
            follow_redirects=False, timeout=httpx.Timeout(15.0, connect=5.0)
        ) as client:
            for page_number in range(MAX_PAGES):
                if page_number:
                    await asyncio.sleep(0.5)  # avoid hammering Telegram previews
                kwargs = {"headers": {"User-Agent": "Mozilla/5.0 (compatible; UniversityIngestion/1.0)"}}
                if oldest_id is not None:
                    kwargs["params"] = {"before": oldest_id}
                response = await client.get(f"https://t.me/s/{username}", **kwargs)
                if response.is_redirect:
                    raise TelegramFetchError(f"Telegram preview for @{username} redirected")
                response.raise_for_status()
                try:
                    # All returned posts are parsed; not just the first 20 visible ones.
                    page = parse_telegram_html(response.text, channel=username, limit=MAX_SYNC_LIMIT)
                except TelegramFetchError:
                    if not messages:
                        raise
                    break
                if not page:
                    break
                min_seen = min(item.message_id for item in page)
                new = [item for item in page if item.message_id not in messages]
                for item in new:
                    messages[item.message_id] = item
                if len(messages) >= limit or not new:
                    break
                if oldest_id is not None and min_seen >= oldest_id:
                    break  # server ignored ?before= or returned same page
                oldest_id = min_seen
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise TelegramFetchError(f"Could not fetch public preview for @{username}: {exc}") from exc

    # Prefer most recent text entries when more are returned than requested.
    return sorted(messages.values(), key=lambda item: item.message_id)[-limit:]
