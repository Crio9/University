"""ingestion, saved posts and canonical codes

Revision ID: 0002_ingestion
Revises: 0001_initial_schema
Create Date: 2026-10-23

Adds:
  * ``raw_contents`` table (ingestion layer) with processing status.
  * ``user_saved_posts`` many-to-many link for saved publications.
  * new ``posts`` columns: ``summary``, ``ai_confidence``, ``raw_content_id``.
  * ``categories.code`` / ``tags.code`` for the canonical AI vocabulary.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_ingestion"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_contents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        # Matches the model: JSONB on PostgreSQL, plain JSON elsewhere.
        sa.Column("ingest_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "external_id",
            name="uq_raw_contents_source_type_external_id",
        ),
    )
    op.create_index(
        op.f("ix_raw_contents_id"), "raw_contents", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_raw_contents_source_type"),
        "raw_contents",
        ["source_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_raw_contents_status"), "raw_contents", ["status"], unique=False
    )

    op.add_column("posts", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("posts", sa.Column("ai_confidence", sa.Float(), nullable=True))
    op.add_column("posts", sa.Column("raw_content_id", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_posts_raw_content_id", "posts", ["raw_content_id"]
    )
    op.create_foreign_key(
        "fk_posts_raw_content_id_raw_contents",
        "posts",
        "raw_contents",
        ["raw_content_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("categories", sa.Column("code", sa.String(length=32), nullable=True))
    op.create_index(
        op.f("ix_categories_code"), "categories", ["code"], unique=True
    )

    op.add_column("tags", sa.Column("code", sa.String(length=32), nullable=True))
    op.create_index(op.f("ix_tags_code"), "tags", ["code"], unique=True)

    op.create_table(
        "user_saved_posts",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "post_id"),
    )


def downgrade() -> None:
    op.drop_table("user_saved_posts")

    op.drop_index(op.f("ix_tags_code"), table_name="tags")
    op.drop_column("tags", "code")

    op.drop_index(op.f("ix_categories_code"), table_name="categories")
    op.drop_column("categories", "code")

    op.drop_constraint(
        "fk_posts_raw_content_id_raw_contents", "posts", type_="foreignkey"
    )
    op.drop_constraint("uq_posts_raw_content_id", "posts", type_="unique")
    op.drop_column("posts", "raw_content_id")
    op.drop_column("posts", "ai_confidence")
    op.drop_column("posts", "summary")

    op.drop_index(op.f("ix_raw_contents_status"), table_name="raw_contents")
    op.drop_index(op.f("ix_raw_contents_source_type"), table_name="raw_contents")
    op.drop_index(op.f("ix_raw_contents_id"), table_name="raw_contents")
    op.drop_table("raw_contents")
