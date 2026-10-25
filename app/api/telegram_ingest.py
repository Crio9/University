"""Staff/admin endpoints for ingesting public Telegram channel messages."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies.auth import require_roles
from app.models.user import User
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

router = APIRouter(prefix="/ingest", tags=["ingest"])
require_staff = require_roles("staff", "admin")


async def _persist(
    db: AsyncSession, channels: list[str], messages: list[TelegramMessage]
) -> TelegramSyncResponse:
    try:
        inserted, duplicates = await store_telegram_messages(db, messages)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
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
    _staff: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> TelegramSyncResponse:
    """Fetch recent messages from one or more PUBLIC channels and save as pending."""
    channels = data.channel_names
    messages: list[TelegramMessage] = []
    try:
        for channel in channels:
            messages.extend(await fetch_channel_messages(channel, data.limit))
    except TelegramFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await _persist(db, channels, messages)


@router.post("/import", response_model=TelegramSyncResponse)
async def import_telegram(
    data: TelegramImportRequest,
    _staff: User = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
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
    return await _persist(db, [data.channel], messages)
