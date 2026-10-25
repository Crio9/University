"""Staff/admin endpoints for ingesting public Telegram channel messages."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import require_roles
from app.models.user import User
from app.models.raw_content import RawContent
from app.schemas.telegram_ingest import (
    TelegramImportRequest,
    TelegramSyncRequest,
    TelegramSyncResponse,
)
from app.services.telegram_source import (
    TelegramFetchError,
    TelegramMessage,
    fetch_channel_messages,
)
from app.services.telegram_storage import store_telegram_messages
from app.services.processing import get_processing_session_factory, process_raw_ids

router = APIRouter(prefix="/ingest", tags=["ingest"])
require_staff = require_roles("staff", "admin")


async def _persist(
    db: AsyncSession,
    channels: list[str],
    messages: list[TelegramMessage],
    background_tasks: BackgroundTasks,
    session_factory,
) -> TelegramSyncResponse:
    try:
        inserted, duplicates = await store_telegram_messages(db, messages)
        raw_ids = list(
            await db.scalars(
                select(RawContent.id).where(
                    RawContent.source_type == "telegram",
                    RawContent.external_id.in_(
                        [message.external_id for message in messages]
                    ),
                    RawContent.status == "pending",
                )
            )
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    background_tasks.add_task(process_raw_ids, raw_ids, session_factory)
    return TelegramSyncResponse(
        channel=channels[0] if len(channels) == 1 else None,
        channels=channels,
        received=len(messages),
        inserted=inserted,
        duplicates=duplicates,
    )


@router.post("/sync", response_model=TelegramSyncResponse)
async def sync_telegram(
    data: TelegramSyncRequest,
    background_tasks: BackgroundTasks,
    _staff: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
    session_factory=Depends(get_processing_session_factory),
) -> TelegramSyncResponse:
    """Fetch recent messages from one or more PUBLIC channels and save as pending."""
    channels = data.channel_names
    messages: list[TelegramMessage] = []
    try:
        for channel in channels:
            messages.extend(await fetch_channel_messages(channel, data.limit))
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
    """Fallback for blocked public previews: import already-extracted JSON."""
    messages = [
        TelegramMessage(
            channel=data.channel,
            message_id=item.message_id,
            text=item.text,
            published_at=item.published_at,
        )
        for item in data.messages
    ]
    return await _persist(
        db, [data.channel], messages, background_tasks, session_factory
    )
