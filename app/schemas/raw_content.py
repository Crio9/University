from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.raw_content import RawContentStatus


class RawContentCreate(BaseModel):
    """Manual/ingestion entry point for a raw publication."""

    source_type: str = Field(min_length=1, max_length=64)
    external_id: str | None = Field(default=None, max_length=255)
    raw_text: str = Field(min_length=1)
    source_url: str | None = Field(default=None, max_length=1024)
    source_published_at: datetime | None = None
    ingest_metadata: dict | None = None


class RawContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: str
    external_id: str | None = None
    raw_text: str
    source_url: str | None = None
    source_published_at: datetime | None = None
    ingest_metadata: dict | None = None
    status: RawContentStatus
    processing_error: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
