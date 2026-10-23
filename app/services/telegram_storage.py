"""Insert Telegram messages as RawContent, without invoking classification."""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.raw_content import RawContent, RawContentStatus
from app.services.telegram_source import TelegramMessage


def store_telegram_messages(db: Session, messages: list[TelegramMessage]) -> tuple[int, int]:
    """Return (inserted, duplicates); caller commits or rolls back the batch.

    PostgreSQL's unique constraint protects against concurrent repeated imports.
    Existing rows are never modified or re-classified.
    """
    inserted = 0
    duplicates = 0
    for message in messages:
        statement = (
            insert(RawContent)
            .values(
                id=uuid.uuid4(),
                source_type="telegram",
                external_id=message.external_id,
                raw_text=message.text,
                source_url=message.source_url,
                source_published_at=message.published_at,
                ingest_metadata={
                    "channel": message.channel,
                    "message_id": message.message_id,
                },
                status=RawContentStatus.PENDING,
            )
            .on_conflict_do_nothing(constraint="uq_raw_contents_source_type_external_id")
            .returning(RawContent.id)
        )
        if db.execute(statement).scalar_one_or_none() is None:
            duplicates += 1
        else:
            inserted += 1
    return inserted, duplicates
