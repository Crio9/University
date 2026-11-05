"""Batch-idempotent storage for Telegram RawContent on PostgreSQL and SQLite."""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_content import RawContent, RawContentStatus
from app.services.telegram_source import TelegramMessage

BATCH_SIZE = 100


async def store_telegram_messages(db: AsyncSession, messages: list[TelegramMessage]) -> tuple[int, int]:
    """Insert in bounded batches; repeated IDs keep their first stored payload.

    Counts duplicates within a single request and against persisted rows.
    """
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = pg_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise RuntimeError(f"Unsupported ingestion database dialect: {dialect}")

    inserted = 0
    for start in range(0, len(messages), BATCH_SIZE):
        batch = messages[start : start + BATCH_SIZE]
        rows = [
            dict(
                source_type="telegram",
                external_id=item.external_id,
                raw_text=item.text,
                source_url=item.source_url,
                source_published_at=item.published_at,
                ingest_metadata={"channel": item.channel, "message_id": item.message_id},
                status=RawContentStatus.PENDING.value,
            )
            for item in batch
        ]
        statement = (insert(RawContent).values(rows)
                     .on_conflict_do_nothing(index_elements=["source_type", "external_id"])
                     .returning(RawContent.id))
        result = await db.execute(statement)
        inserted += len(result.scalars().all())
    return inserted, len(messages) - inserted
