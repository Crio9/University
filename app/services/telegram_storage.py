"""Persist Telegram messages using the existing async RawContent model.

PostgreSQL/SQLite ON CONFLICT makes repeated and concurrent imports idempotent.
No classification or Post creation is triggered in this source adapter.
"""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_content import RawContent, RawContentStatus
from app.services.telegram_source import TelegramMessage


async def store_telegram_messages(
    db: AsyncSession, messages: list[TelegramMessage]
) -> tuple[int, int]:
    """Write pending rows without modifying duplicates; return inserted, duplicate."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = pg_insert
    elif dialect == "sqlite":
        insert = sqlite_insert  # Test backend.
    else:
        raise RuntimeError(f"Unsupported ingestion database dialect: {dialect}")

    inserted = duplicates = 0
    for message in messages:
        statement = (
            insert(RawContent)
            .values(
                source_type="telegram",
                external_id=message.external_id,
                raw_text=message.text,
                source_url=message.source_url,
                source_published_at=message.published_at,
                ingest_metadata={
                    "channel": message.channel,
                    "message_id": message.message_id,
                },
                status=RawContentStatus.PENDING.value,
            )
            .on_conflict_do_nothing(
                index_elements=["source_type", "external_id"]
            )
            .returning(RawContent.id)
        )
        result = await db.execute(statement)
        if result.scalar_one_or_none() is None:
            duplicates += 1
        else:
            inserted += 1
    return inserted, duplicates
