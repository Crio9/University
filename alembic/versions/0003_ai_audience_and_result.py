"""Keep complete AI targeting and the classification result for review."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_ai_audience"
down_revision = "0002_ingestion"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "posts", sa.Column("target_audience", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "raw_contents", sa.Column("ai_result", postgresql.JSONB(), nullable=True)
    )


def downgrade():
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT id, target_audience FROM posts WHERE target_audience IS NOT NULL"
            )
        ).mappings()
    )
    for row in rows:
        audience = row["target_audience"]
        if audience.get("group") or any(
            len(audience.get(key, [])) > 1 for key in ("faculty", "program", "course")
        ):
            raise RuntimeError(
                "Cannot downgrade: structured audience cannot be represented by legacy fields"
            )
    for row in rows:
        audience = row["target_audience"]
        bind.execute(
            sa.text(
                "UPDATE posts SET target_faculty=:faculty, target_program=:program, target_course=:course WHERE id=:id"
            ),
            {
                key: (audience.get(key) or [None])[0]
                for key in ("faculty", "program", "course")
            }
            | {"id": row["id"]},
        )
    op.drop_column("raw_contents", "ai_result")
    op.drop_column("posts", "target_audience")
