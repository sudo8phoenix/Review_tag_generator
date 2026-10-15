"""Track full-review annotation revisions and progress."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0005_review_annotations'
down_revision = '0004_review_corrections'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('review_annotations',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('analysis_run_id', sa.Uuid(), sa.ForeignKey('analysis_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('snapshot_id', sa.Uuid(), nullable=False),
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('request_sha256', sa.String(64), nullable=False),
        sa.Column('status', sa.String(24), nullable=False),
        sa.Column('reviewer', sa.String(120), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('analysis_run_id', 'request_id', name='uq_annotations_run_request'),
        sa.CheckConstraint("status IN ('needs_review', 'reviewed', 'needs_adjudication')", name='ck_annotations_status'))
    op.create_index('ix_annotations_run_created', 'review_annotations', ['analysis_run_id', 'created_at'])


def downgrade():
    op.drop_table('review_annotations')
