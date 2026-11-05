"""Staff/admin endpoints for public Telegram previews and JSON fallback."""
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import require_roles
from app.models.user import User
from app.models.raw_content import RawContent
from app.schemas.telegram_ingest import TelegramImportRequest, TelegramSyncRequest, TelegramSyncResponse
from app.services.telegram_source import TelegramFetchError, TelegramMessage, fetch_channel_messages
from app.services.telegram_storage import store_telegram_messages
from app.services.processing import get_processing_session_factory, process_raw_ids

router = APIRouter(prefix="/ingest", tags=["ingest"])
require_staff = require_roles("staff", "admin")
MAX_AUTO_PROCESS_IDS = 100  # Larger imports remain durable and can use /process-pending.


async def _persist(
    db: AsyncSession,
    channels: list[str],
    messages: list[TelegramMessage],
    background_tasks: BackgroundTasks,
    session_factory,
) -> TelegramSyncResponse:
    try:
        inserted, duplicates = await store_telegram_messages(db, messages)
        raw_ids = []
        # Bounded IN clauses are portable to SQLite and PostgreSQL.
        ids = [message.external_id for message in messages]
        for offset in range(0, len(ids), 200):
            if len(raw_ids) >= MAX_AUTO_PROCESS_IDS:
                break
            new_ids = await db.scalars(
                select(RawContent.id).where(
                    RawContent.source_type == "telegram",
                    RawContent.external_id.in_(ids[offset : offset + 200]),
                    RawContent.status == "pending",
                ).order_by(RawContent.id).limit(MAX_AUTO_PROCESS_IDS - len(raw_ids))
            )
            raw_ids.extend(new_ids.all())
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    if raw_ids:
        background_tasks.add_task(process_raw_ids, list(dict.fromkeys(raw_ids)), session_factory)
    return TelegramSyncResponse(
        channel=channels[0] if len(channels) == 1 else None,
        channels=channels,
        received=len(messages), inserted=inserted, duplicates=duplicates,
    )


@router.post("/sync", response_model=TelegramSyncResponse)
async def sync_telegram(
    data: TelegramSyncRequest,
    background_tasks: BackgroundTasks,
    _staff: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    session_factory=Depends(get_processing_session_factory),
) -> TelegramSyncResponse:
    """Fetch up to 300 recent visible text posts from each public channel."""
    channels = data.channel_names
    limit = asyncio.Semaphore(3)

    async def fetch_one(channel: str) -> list[TelegramMessage]:
        async with limit:
            return await fetch_channel_messages(channel, data.limit)

    try:
        pages = await asyncio.gather(*(fetch_one(channel) for channel in channels))
        messages = [item for page in pages for item in page]
    except TelegramFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await _persist(db, channels, messages, background_tasks, session_factory)


@router.post("/import", response_model=TelegramSyncResponse)
async def import_telegram(
    data: TelegramImportRequest,
    background_tasks: BackgroundTasks,
    _staff: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    session_factory=Depends(get_processing_session_factory),
) -> TelegramSyncResponse:
    """Import up to 1000 previously extracted messages as JSON."""
    messages = [
        TelegramMessage(data.channel, item.message_id, item.text, item.published_at)
        for item in data.messages
    ]
    return await _persist(db, [data.channel], messages, background_tasks, session_factory)
