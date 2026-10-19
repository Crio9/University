import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

post_tags = Table(
    "post_tags",
    Base.metadata,
    Column(
        "post_id",
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    raw_content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_contents.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Targeting: empty array means "all"
    target_roles: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    target_faculties: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    target_courses: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, default=list
    )

    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
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

    category = relationship("Category", back_populates="posts")
    author = relationship("User", back_populates="posts")
    raw_content = relationship("RawContent", back_populates="post")
    tags = relationship("Tag", secondary=post_tags, lazy="selectin")
    saved_by = relationship(
        "UserSavedPost", back_populates="post", cascade="all, delete-orphan"
    )
