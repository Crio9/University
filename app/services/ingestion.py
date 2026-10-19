"""Ingestion layer: persist raw source content idempotently.

The public entry point is :func:`ingest_raw_content`. Re-importing the same
source item must not create a duplicate, so items carrying an ``external_id``
are de-duplicated on ``(source_type, external_id)``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.raw_content import RawContent, RawContentStatus
from app.schemas.raw_content import RawContentCreate


def ingest_raw_content(db: Session, data: RawContentCreate) -> RawContent:
    """Create (or return the existing) raw content row for the given item."""
    if data.external_id:
        existing = (
            db.query(RawContent)
            .filter(
                RawContent.source_type == data.source_type,
                RawContent.external_id == data.external_id,
            )
            .first()
        )
        if existing is not None:
            return existing

    raw = RawContent(
        source_type=data.source_type,
        external_id=data.external_id,
        raw_text=data.raw_text,
        source_url=data.source_url,
        source_published_at=data.source_published_at,
        ingest_metadata=data.ingest_metadata,
        status=RawContentStatus.PENDING,
    )
    db.add(raw)
    db.flush()
    return raw
