"""Persist immutable inference payloads and job product ownership."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_runtime_payload"
down_revision = "0001_initial_postgres_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('uq_snapshot_product_version_revision', 'product_snapshots', type_='unique')
    op.create_unique_constraint('uq_snapshot_product_version_revision', 'product_snapshots',
        ['product_id', 'pipeline_version', 'aggregate_version', 'data_revision'])
    op.add_column("analysis_runs", sa.Column("payload", postgresql.JSONB(), nullable=True))
    op.add_column("processing_jobs", sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=True))


def downgrade():
    op.drop_constraint('uq_snapshot_product_version_revision', 'product_snapshots', type_='unique')
    op.create_unique_constraint('uq_snapshot_product_version_revision', 'product_snapshots',
        ['product_id', 'aggregate_version', 'data_revision'])
    op.drop_column("processing_jobs", "product_id")
    op.drop_column("analysis_runs", "payload")
