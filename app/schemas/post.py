from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class CategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class PostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    category_id: UUID
    tag_ids: list[UUID] = []
    target_roles: list[str] = []
    target_faculties: list[str] = []
    target_courses: list[int] = []
    deadline: datetime | None = None
    is_published: bool = True


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    body: str
    summary: str | None = None
    category: CategoryRead
    tags: list[TagRead] = []
    target_roles: list[str] = []
    target_faculties: list[str] = []
    target_courses: list[int] = []
    deadline: datetime | None = None
    ai_confidence: float | None = None
    is_published: bool
    is_saved: bool = False
    published_at: datetime
    author_id: UUID
