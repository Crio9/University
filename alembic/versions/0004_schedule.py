"""Independent schedule for develop; team merge will reconcile with 0004_university.

Revision ID: 0004_schedule
Revises: 0003_ai_audience
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_schedule"
down_revision: Union[str, None] = "0003_ai_audience"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schedule_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_key", sa.String(64), nullable=False),
        sa.Column("university", sa.String(255), nullable=False),
        sa.Column("faculty", sa.String(255), nullable=False),
        sa.Column("study_program", sa.String(255), nullable=False),
        sa.Column("study_group", sa.String(100), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("room", sa.String(100), nullable=True),
        sa.Column("teacher", sa.String(255), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("original_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_schedule_ends_after_start"),
        sa.CheckConstraint("status IN ('NORMAL', 'MOVED', 'CANCELLED')", name="ck_schedule_status"),
    )
    op.create_index("ix_schedule_group_start", "schedule_entries", ["group_key", "starts_at"])
    op.create_index("ix_schedule_group_original", "schedule_entries", ["group_key", "original_starts_at"])
    op.create_table(
        "staff_schedule_groups",
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_key", sa.String(64), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("staff_schedule_groups")
    op.drop_index("ix_schedule_group_original", table_name="schedule_entries")
    op.drop_index("ix_schedule_group_start", table_name="schedule_entries")
    op.drop_table("schedule_entries")
