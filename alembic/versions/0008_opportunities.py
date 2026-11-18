"""Student opportunity preferences and independently reviewed source records."""
from alembic import op
import sqlalchemy as sa

revision = "0008_opportunities"
down_revision = "0007_merge_appeals_schedule"
branch_labels = depends_on = None


def upgrade():
    op.add_column("student_profiles", sa.Column("catalog_program_id", sa.Integer(), sa.ForeignKey("study_programs.id")))
    op.add_column("student_profiles", sa.Column("preferred_types", sa.JSON()))
    op.add_column("raw_contents", sa.Column("opportunity_review", sa.JSON()))


def downgrade():
    op.drop_column("raw_contents", "opportunity_review")
    op.drop_column("student_profiles", "preferred_types")
    op.drop_column("student_profiles", "catalog_program_id")
