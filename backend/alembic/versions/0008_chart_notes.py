"""Allow chart notes on every page and at whole-course scope."""
from alembic import op
import sqlalchemy as sa

revision = "0008_chart_notes"
down_revision = "0007_insight_notes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("insight_notes", sa.Column("scope_key", sa.String(120), nullable=False, server_default=""))
    op.execute("UPDATE insight_notes n JOIN course_offerings o ON n.offering_id=o.id SET n.scope_key=o.offering_code")
    op.drop_constraint(op.f("ck_insight_notes_chart_key"), "insight_notes", type_="check")
    op.drop_constraint("uq_insight_notes_scope_chart", "insight_notes", type_="unique")
    op.alter_column("insight_notes", "offering_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("insight_notes", "chart_key", existing_type=sa.String(64), type_=sa.String(160), nullable=False)
    op.create_unique_constraint("uq_insight_notes_scope_chart", "insight_notes", ["course_id", "scope_key", "chart_key"])
    op.alter_column("insight_notes", "scope_key", existing_type=sa.String(120), server_default=None)


def downgrade():
    # Older versions support only the original assignment chart.
    op.execute("DELETE FROM insight_notes WHERE offering_id IS NULL OR chart_key <> 'assignment_submission_timing'")
    op.drop_constraint("uq_insight_notes_scope_chart", "insight_notes", type_="unique")
    op.alter_column("insight_notes", "offering_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("insight_notes", "chart_key", existing_type=sa.String(160), type_=sa.String(64), nullable=False)
    op.create_unique_constraint("uq_insight_notes_scope_chart", "insight_notes", ["course_id", "offering_id", "chart_key"])
    op.create_check_constraint("chart_key", "insight_notes", "chart_key IN ('assignment_submission_timing')")
    op.drop_column("insight_notes", "scope_key")
