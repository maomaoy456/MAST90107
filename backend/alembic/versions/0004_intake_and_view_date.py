"""Separate first-view calendar dates from instants and intake month labels."""
from alembic import op
import sqlalchemy as sa

revision = "0004_intake_and_view_date"
down_revision = "0003_timestamp_precision"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("course_offerings", sa.Column("offering_code", sa.String(120), nullable=True))
    op.add_column("course_offerings", sa.Column("intake_year", sa.Integer(), nullable=True))
    op.add_column("course_offerings", sa.Column("intake_month", sa.Integer(), nullable=True))
    op.add_column("course_offerings", sa.Column("cohort_label", sa.String(32), nullable=True))
    op.add_column("engagement_events", sa.Column("first_viewed_on", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("engagement_events", "first_viewed_on")
    for name in ("cohort_label", "intake_month", "intake_year", "offering_code"):
        op.drop_column("course_offerings", name)
