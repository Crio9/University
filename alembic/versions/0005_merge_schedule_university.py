"""Join the independently deployed Sprint 3 schedule and university branches.

Revision ID: 0005_merge_s3
Revises: 0004_schedule, 0004_university

This is a graph-only merge: both 0004 branches have to run before the
next migration can safely reference study_groups from schedule_entries.
"""
from typing import Sequence, Union

revision: str = "0005_merge_s3"
down_revision: Union[str, tuple[str, str]] = (
    "0004_schedule",
    "0004_university",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
