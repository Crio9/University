
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f51945960259"
down_revision: Union[str, None] = "0004_university"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "appeals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="CREATED",
            nullable=False,
        ),
        sa.Column("staff_response", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_appeals_id",
        "appeals",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_appeals_student_id",
        "appeals",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        "ix_appeals_staff_id",
        "appeals",
        ["staff_id"],
        unique=False,
    )
    op.create_index(
        "ix_appeals_status",
        "appeals",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_appeals_status", table_name="appeals")
    op.drop_index("ix_appeals_staff_id", table_name="appeals")
    op.drop_index("ix_appeals_student_id", table_name="appeals")
    op.drop_index("ix_appeals_id", table_name="appeals")
    op.drop_table("appeals")
