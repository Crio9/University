from datetime import datetime

from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.dictionaries import Tag

post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Short AI-generated summary (see classification rules, section 7).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Provenance of AI-processed content; NULL for manually created posts.
    raw_content_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_contents.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    importance: Mapped[str] = mapped_column(
        String(20), nullable=False, default="standard"
    )
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    target_faculty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_program: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_course: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Complete AI audience; NULL retains the original single-value API behavior.
    target_audience: Mapped[dict | None] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tags: Mapped[list["Tag"]] = relationship(
        secondary=post_tags,
        lazy="selectin",
    )
    raw_content = relationship("RawContent", back_populates="post")
