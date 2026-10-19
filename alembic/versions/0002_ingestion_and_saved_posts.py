"""ingestion and saved posts.

Revision ID: 0002_ingestion
Revises: 0001_initial
Create Date: 2026-10-20

Adds:
  * ``raw_contents`` table (ingestion layer) with processing status enum.
  * ``user_saved_posts`` many-to-many link for saved publications.
  * new ``posts`` columns: ``summary``, ``ai_confidence``, ``raw_content_id``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_ingestion"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    raw_content_status = postgresql.ENUM(
        "pending",
        "processed",
        "failed",
        "needs_review",
        name="raw_content_status",
        create_type=True,
    )
    raw_content_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "raw_contents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingest_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processed",
                "failed",
                "needs_review",
                name="raw_content_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type", "external_id", name="uq_raw_contents_source_type_external_id"
        ),
    )
    op.create_index(
        op.f("ix_raw_contents_source_type"), "raw_contents", ["source_type"], unique=False
    )
    op.create_index(op.f("ix_raw_contents_status"), "raw_contents", ["status"], unique=False)

    op.add_column("posts", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("ai_confidence", sa.Float(), nullable=True))
    op.add_column(
        "posts",
        sa.Column("raw_content_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_posts_raw_content_id", "posts", ["raw_content_id"])
    op.create_foreign_key(
        "fk_posts_raw_content_id_raw_contents",
        "posts",
        "raw_contents",
        ["raw_content_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "user_saved_posts",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id"),
    )


def downgrade() -> None:
    op.drop_table("user_saved_posts")

    op.drop_constraint("fk_posts_raw_content_id_raw_contents", "posts", type_="foreignkey")
    op.drop_constraint("uq_posts_raw_content_id", "posts", type_="unique")
    op.drop_column("posts", "raw_content_id")
    op.drop_column("posts", "ai_confidence")
    op.drop_column("posts", "summary")

    op.drop_index(op.f("ix_raw_contents_status"), table_name="raw_contents")
    op.drop_index(op.f("ix_raw_contents_source_type"), table_name="raw_contents")
    op.drop_table("raw_contents")
    op.execute("DROP TYPE IF EXISTS raw_content_status")
