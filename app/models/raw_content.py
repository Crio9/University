import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RawContentStatus(str, enum.Enum):
    """Processing lifecycle of a raw ingested message."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class RawContent(Base):
    """Original message pulled from an external source before classification.

    The raw text and its provenance are kept so the AI result can be audited
    and re-processed without losing the source data.
    """

    __tablename__ = "raw_contents"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "external_id",
            name="uq_raw_contents_source_type_external_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingest_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[RawContentStatus] = mapped_column(
        Enum(
            RawContentStatus,
            name="raw_content_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=RawContentStatus.PENDING,
        index=True,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    post = relationship("Post", back_populates="raw_content", uselist=False)
