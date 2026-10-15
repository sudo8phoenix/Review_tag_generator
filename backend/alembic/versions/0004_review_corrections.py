"""Store source-linked suggestions and append-only reviewer decisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0004_review_corrections'
down_revision = '0003_saved_data_management'
branch_labels = None
depends_on = None


def upgrade():
    for name in ('review_suggestions', 'review_corrections'):
        columns = [
            sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('analysis_run_id', sa.Uuid(), sa.ForeignKey('analysis_runs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('snapshot_id', sa.Uuid(), nullable=False),
            sa.Column('start_char', sa.Integer(), nullable=False),
            sa.Column('end_char', sa.Integer(), nullable=False),
            sa.Column('payload', postgresql.JSONB(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        ]
        if name == 'review_corrections':
            columns.extend([
                sa.Column('request_id', sa.Uuid(), nullable=False),
                sa.Column('request_sha256', sa.String(64), nullable=False),
                sa.Column('decision', sa.String(8), nullable=False),
                sa.Column('reviewer', sa.String(120), nullable=False),
                sa.Column('reason', sa.Text(), nullable=False),
                sa.UniqueConstraint('analysis_run_id', 'request_id', name='uq_corrections_run_request'),
                sa.CheckConstraint("decision IN ('accepted', 'edited', 'rejected')", name='ck_corrections_decision'),
            ])
        op.create_table(name, *columns)
    op.create_index('ix_suggestions_run_span', 'review_suggestions', ['analysis_run_id', 'start_char', 'end_char'])
    op.create_index('ix_corrections_run_span_created', 'review_corrections', ['analysis_run_id', 'start_char', 'end_char', 'created_at'])


def downgrade():
    op.drop_table('review_corrections')
    op.drop_table('review_suggestions')
