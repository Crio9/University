"""Ingestion layer: persist raw source content idempotently.

The public entry point is :func:`ingest_raw_content`. Re-importing the same
source item must not create a duplicate, so items carrying an ``external_id``
are de-duplicated on ``(source_type, external_id)``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_content import RawContent, RawContentStatus
from app.schemas.raw_content import RawContentCreate


async def ingest_raw_content(db: AsyncSession, data: RawContentCreate) -> RawContent:
    """Create (or return the existing) raw content row for the given item."""
    if data.external_id is not None:
        dialect = db.get_bind().dialect.name
        insert = pg_insert if dialect == "postgresql" else sqlite_insert
        await db.execute(
            insert(RawContent)
            .values(
                **data.model_dump(),
                status=RawContentStatus.PENDING.value,
            )
            .on_conflict_do_nothing(index_elements=["source_type", "external_id"])
        )
        return (
            await db.scalars(
                select(RawContent).where(
                    RawContent.source_type == data.source_type,
                    RawContent.external_id == data.external_id,
                )
            )
        ).one()

    raw = RawContent(
        source_type=data.source_type,
        external_id=data.external_id,
        raw_text=data.raw_text,
        source_url=data.source_url,
        source_published_at=data.source_published_at,
        ingest_metadata=data.ingest_metadata,
        status=RawContentStatus.PENDING.value,
    )
    db.add(raw)
    await db.flush()
    return raw
