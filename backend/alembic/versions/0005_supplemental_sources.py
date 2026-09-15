"""supplemental_sources

Revision ID: 0005_supplemental_sources
Revises: 0004_intake_and_view_date
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = '0005_supplemental_sources'
down_revision = '0004_intake_and_view_date'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('support_cases',
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('source_row', sa.Integer(), nullable=False),
    sa.Column('opened_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), nullable=False),
    sa.Column('response_hours', sa.Numeric(precision=16, scale=4), nullable=True),
    sa.Column('is_open', sa.Boolean(), nullable=True),
    sa.Column('is_closed', sa.Boolean(), nullable=True),
    sa.Column('channel', sa.String(length=64), nullable=False),
    sa.Column('subject', sa.String(length=2000), nullable=True),
    sa.Column('source_fields', sa.JSON(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.CheckConstraint('response_hours IS NULL OR response_hours >= 0', name=op.f('ck_support_cases_response_hours')),
    sa.ForeignKeyConstraint(['batch_id'], ['import_batches.id'], name=op.f('fk_support_cases_batch_id_import_batches')),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], name=op.f('fk_support_cases_course_id_courses')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_support_cases')),
    sa.UniqueConstraint('batch_id', 'source_row', name=op.f('uq_support_cases_batch_id'))
    )
    op.create_index(op.f('ix_support_cases_batch_id'), 'support_cases', ['batch_id'], unique=False)
    op.create_index(op.f('ix_support_cases_course_id'), 'support_cases', ['course_id'], unique=False)
    op.create_table('offering_calendars',
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('offering_id', sa.Integer(), nullable=False),
    sa.Column('starts_on', sa.Date(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=False),
    sa.Column('enrolment_records', sa.Integer(), nullable=False),
    sa.Column('withdrawn_records', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.CheckConstraint('ends_on >= starts_on', name=op.f('ck_offering_calendars_dates')),
    sa.CheckConstraint('enrolment_records >= withdrawn_records AND withdrawn_records >= 0', name=op.f('ck_offering_calendars_counts')),
    sa.ForeignKeyConstraint(['batch_id'], ['import_batches.id'], name=op.f('fk_offering_calendars_batch_id_import_batches')),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], name=op.f('fk_offering_calendars_offering_id_course_offerings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_offering_calendars')),
    sa.UniqueConstraint('batch_id', 'offering_id', name=op.f('uq_offering_calendars_batch_id'))
    )
    op.create_index(op.f('ix_offering_calendars_batch_id'), 'offering_calendars', ['batch_id'], unique=False)
    op.create_table('survey_responses',
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('offering_id', sa.Integer(), nullable=False),
    sa.Column('response_digest', sa.String(length=64), nullable=False),
    sa.Column('finished', sa.Boolean(), nullable=False),
    sa.Column('recorded_at', sa.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'), nullable=True),
    sa.Column('nps', sa.Integer(), nullable=True),
    sa.Column('answers', sa.JSON(), nullable=False),
    sa.Column('feedback', sa.JSON(), nullable=False),
    sa.Column('source_fields', sa.JSON(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.CheckConstraint('nps IS NULL OR (nps >= 0 AND nps <= 10)', name=op.f('ck_survey_responses_nps')),
    sa.ForeignKeyConstraint(['batch_id'], ['import_batches.id'], name=op.f('fk_survey_responses_batch_id_import_batches')),
    sa.ForeignKeyConstraint(['offering_id'], ['course_offerings.id'], name=op.f('fk_survey_responses_offering_id_course_offerings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_survey_responses')),
    sa.UniqueConstraint('batch_id', 'response_digest', name=op.f('uq_survey_responses_batch_id'))
    )
    op.create_index(op.f('ix_survey_responses_batch_id'), 'survey_responses', ['batch_id'], unique=False)
    op.create_index(op.f('ix_survey_responses_offering_id'), 'survey_responses', ['offering_id'], unique=False)
    op.add_column('import_batches', sa.Column('scope', sa.String(length=160), server_default='global', nullable=False))

def downgrade():
    op.drop_column('import_batches', 'scope')
    op.drop_table('survey_responses')
    op.drop_table('offering_calendars')
    op.drop_table('support_cases')
