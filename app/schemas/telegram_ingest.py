"""Transport schemas for public Telegram sync and normalized JSON import."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.telegram_source import clean_channel


class ChannelRequest(BaseModel):
    channel: str

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        return clean_channel(value)


class TelegramSyncRequest(ChannelRequest):
    limit: int = Field(default=20, ge=1, le=50)


class ImportMessage(BaseModel):
    message_id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=200000)
    published_at: datetime | None = None


class TelegramImportRequest(ChannelRequest):
    messages: list[ImportMessage] = Field(min_length=1, max_length=100)


class TelegramSyncResponse(BaseModel):
    channel: str
    received: int
    inserted: int
    duplicates: int
