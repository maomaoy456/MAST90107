"""Keep millisecond precision in normalized UTC timestamps."""
from alembic import op
from sqlalchemy.dialects import mysql

revision = "0003_timestamp_precision"
down_revision = "0002_import_fields"
branch_labels = None
depends_on = None

COLUMNS = {
    "engagement_events": ["occurred_at", "first_viewed_at", "last_viewed_at"],
    "assignment_submissions": ["submitted_at", "graded_at"],
    "badge_awards": ["awarded_at", "expires_at"],
}


def upgrade():
    for table, columns in COLUMNS.items():
        for column in columns:
            op.alter_column(table, column, existing_type=mysql.DATETIME(),
                            type_=mysql.DATETIME(fsp=3), existing_nullable=True)


def downgrade():
    # MySQL rounds fractional seconds when reducing precision; forbid on populated stores.
    if not op.get_context().as_sql:
        import sqlalchemy as sa
        for table in COLUMNS:
            if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
                raise RuntimeError("Precision downgrade requires an empty observation store")
    for table, columns in COLUMNS.items():
        for column in columns:
            op.alter_column(table, column, existing_type=mysql.DATETIME(fsp=3),
                            type_=mysql.DATETIME(), existing_nullable=True)
