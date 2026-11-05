"""Telegram ingestion request/response contracts, including bulk import."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services.telegram_source import clean_channel, MAX_SYNC_LIMIT


class TelegramSyncRequest(BaseModel):
    channel: str | None = None
    channels: list[str] | None = Field(default=None, min_length=1, max_length=20)
    limit: int = Field(default=20, ge=1, le=MAX_SYNC_LIMIT)

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, value: str | None) -> str | None:
        return clean_channel(value) if value is not None else None

    @field_validator("channels")
    @classmethod
    def normalize_channels(cls, value: list[str] | None) -> list[str] | None:
        return list(dict.fromkeys(clean_channel(channel) for channel in value)) if value is not None else None

    @model_validator(mode="after")
    def validate_source(self):
        if (self.channel is None) == (self.channels is None):
            raise ValueError("Provide exactly one of 'channel' or 'channels'")
        return self

    @property
    def channel_names(self) -> list[str]:
        return [self.channel] if self.channel is not None else (self.channels or [])


class TelegramImportItem(BaseModel):
    message_id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=200000)
    published_at: datetime | None = None


class TelegramImportRequest(BaseModel):
    channel: str
    messages: list[TelegramImportItem] = Field(min_length=1, max_length=1000)

    @field_validator("channel")
    @classmethod
    def normalize_channel(cls, value: str) -> str:
        return clean_channel(value)


class TelegramSyncResponse(BaseModel):
    channel: str | None = None
    channels: list[str]
    received: int
    inserted: int
    duplicates: int
