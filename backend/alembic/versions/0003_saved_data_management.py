"""Remember one-time demo seeding and imported batch filenames."""
from alembic import op
import sqlalchemy as sa

revision = '0003_saved_data_management'
down_revision = '0002_runtime_payload'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('application_settings',
        sa.Column('key', sa.String(80), primary_key=True),
        sa.Column('value', sa.String(80), nullable=False))
    op.add_column('processing_jobs', sa.Column('input_filename', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('processing_jobs', 'input_filename')
    op.drop_table('application_settings')
