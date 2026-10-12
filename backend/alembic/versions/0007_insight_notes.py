"""Persist editable chart insights per course offering.

Revision ID: 0007_insight_notes
Revises: 0006_model_artifacts
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_insight_notes"
down_revision = "0006_model_artifacts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "insight_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("offering_id", sa.Integer(), sa.ForeignKey("course_offerings.id"), nullable=False),
        sa.Column("chart_key", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("chart_key IN ('assignment_submission_timing')", name=op.f("ck_insight_notes_chart_key")),
        sa.UniqueConstraint("course_id", "offering_id", "chart_key", name=op.f("uq_insight_notes_scope_chart")),
    )
    op.create_index(op.f("ix_insight_notes_course_id"), "insight_notes", ["course_id"])
    op.create_index(op.f("ix_insight_notes_offering_id"), "insight_notes", ["offering_id"])


def downgrade():
    # Dropping the table also removes indexes; MySQL may reject dropping an
    # index first when it is backing a foreign-key constraint.
    op.drop_table("insight_notes")
