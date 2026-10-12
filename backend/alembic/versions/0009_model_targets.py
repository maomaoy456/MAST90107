"""Replace assessment-grade targets with course pass and Badge targets."""
from alembic import op

revision = "0009_model_targets"
down_revision = "0008_chart_notes"
branch_labels = None
depends_on = None


def upgrade():
    # Feature definitions changed for Badge as well, so every v1 run is retired.
    op.execute("DELETE FROM model_runs")
    op.drop_constraint(op.f("ck_model_runs_target"), "model_runs", type_="check")
    op.create_check_constraint(op.f("ck_model_runs_target"), "model_runs", "target IN ('pass','badge')")


def downgrade():
    op.execute("DELETE FROM model_runs")
    op.drop_constraint(op.f("ck_model_runs_target"), "model_runs", type_="check")
    op.create_check_constraint(
        op.f("ck_model_runs_target"), "model_runs",
        "target IN ('AT1','AT2','weighted_final','badge')",
    )
