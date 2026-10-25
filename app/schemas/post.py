from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dictionary import TagRead

Importance = Literal["low", "standard", "high", "critical"]


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    category_id: int = Field(gt=0)
    importance: Importance = "standard"
    deadline: datetime | None = None
    target_faculty: str | None = Field(default=None, max_length=255)
    target_program: str | None = Field(default=None, max_length=255)
    target_course: int | None = Field(default=None, ge=1, le=6)
    tag_ids: list[int] = Field(default_factory=list)


class PostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    category_id: int | None = Field(default=None, gt=0)
    importance: Importance | None = None
    deadline: datetime | None = None
    target_faculty: str | None = Field(default=None, max_length=255)
    target_program: str | None = Field(default=None, max_length=255)
    target_course: int | None = Field(default=None, ge=1, le=6)
    tag_ids: list[int] | None = None


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    summary: str | None = None
    category_id: int
    author_id: int
    importance: Importance
    deadline: datetime | None
    target_faculty: str | None
    target_program: str | None
    target_course: int | None
    ai_confidence: float | None = None
    is_saved: bool = False
    created_at: datetime
    tags: list[TagRead] = Field(default_factory=list)
