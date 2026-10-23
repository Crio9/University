"""Staff-only Telegram collection endpoints, independent of the existing ingest API."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dependencies.auth import require_staff
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


def _persist(
    db: Session, *, channel: str, messages: list[TelegramMessage]
) -> TelegramSyncResponse:
    try:
        inserted, duplicates = store_telegram_messages(db, messages)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return TelegramSyncResponse(
        channel=channel,
        received=len(messages),
        inserted=inserted,
        duplicates=duplicates,
    )


@router.post("/sync", response_model=TelegramSyncResponse)
def sync_telegram(
    data: TelegramSyncRequest,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> TelegramSyncResponse:
    """Fetch newest public messages into raw_contents; AI processes separately."""
    try:
        messages = fetch_channel_messages(data.channel, data.limit)
    except TelegramFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _persist(db, channel=data.channel, messages=messages)


@router.post("/import", response_model=TelegramSyncResponse)
def import_telegram(
    data: TelegramImportRequest,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> TelegramSyncResponse:
    """Import normalized JSON messages when Telegram HTML is inaccessible."""
    messages = [
        TelegramMessage(data.channel, row.message_id, row.text, row.published_at)
        for row in data.messages
    ]
    return _persist(db, channel=data.channel, messages=messages)
