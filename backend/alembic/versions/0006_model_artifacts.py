"""model_artifacts

Revision ID: 0006_model_artifacts
Revises: 0005_supplemental_sources
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_model_artifacts"
down_revision = "0005_supplemental_sources"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_model_runs_cohort_policy"), "model_runs", type_="check")
    op.drop_constraint(op.f("ck_model_runs_status"), "model_runs", type_="check")
    op.add_column("model_runs", sa.Column("course_id", sa.Integer(), nullable=True))
    op.add_column("model_runs", sa.Column("target", sa.String(24), nullable=True))
    op.add_column("model_runs", sa.Column("data_sha256", sa.String(64), server_default="", nullable=False))
    op.add_column("model_runs", sa.Column("artifact_path", sa.String(255), nullable=True))
    op.add_column("model_runs", sa.Column("artifact_sha256", sa.String(64), nullable=True))
    op.add_column("model_runs", sa.Column("metrics", sa.JSON(), nullable=True))
    op.add_column("model_runs", sa.Column("summary", sa.JSON(), nullable=True))
    op.execute("UPDATE model_runs SET cohort_policy='student_grouped', status='failed', target='AT1' WHERE target IS NULL")
    op.alter_column("model_runs", "cohort_policy", existing_type=sa.String(32), server_default="student_grouped")
    op.alter_column("model_runs", "course_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("model_runs", "target", existing_type=sa.String(24), nullable=False)
    op.create_foreign_key(op.f("fk_model_runs_course_id_courses"), "model_runs", "courses", ["course_id"], ["id"])
    op.create_index(op.f("ix_model_runs_course_id"), "model_runs", ["course_id"])
    op.create_index(op.f("ix_model_runs_target"), "model_runs", ["target"])
    op.create_check_constraint(op.f("ck_model_runs_cohort_policy"), "model_runs", "cohort_policy = 'student_grouped'")
    op.create_check_constraint(op.f("ck_model_runs_target"), "model_runs", "target IN ('AT1','AT2','weighted_final','badge')")
    op.create_check_constraint(op.f("ck_model_runs_status"), "model_runs", "status IN ('pending','running','completed','insufficient','failed')")


def downgrade():
    op.drop_constraint(op.f("ck_model_runs_status"), "model_runs", type_="check")
    op.drop_constraint(op.f("ck_model_runs_target"), "model_runs", type_="check")
    op.drop_constraint(op.f("ck_model_runs_cohort_policy"), "model_runs", type_="check")
    op.drop_constraint(op.f("fk_model_runs_course_id_courses"), "model_runs", type_="foreignkey")
    op.drop_index(op.f("ix_model_runs_target"), table_name="model_runs")
    op.drop_index(op.f("ix_model_runs_course_id"), table_name="model_runs")
    for name in ("summary", "metrics", "artifact_sha256", "artifact_path", "data_sha256", "target", "course_id"):
        op.drop_column("model_runs", name)
    op.execute("UPDATE model_runs SET cohort_policy='intersection', status='failed'")
    op.alter_column("model_runs", "cohort_policy", existing_type=sa.String(32), server_default="intersection")
    op.create_check_constraint(op.f("ck_model_runs_cohort_policy"), "model_runs", "cohort_policy = 'intersection'")
    op.create_check_constraint(op.f("ck_model_runs_status"), "model_runs", "status IN ('pending','running','completed','failed')")
