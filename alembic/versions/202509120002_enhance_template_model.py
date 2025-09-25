"""enhance template model with preview and metrics

Revision ID: 202509120002
Revises: 1234567890ab
Create Date: 2025-09-12 00:02:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '202509120002'
down_revision = '1234567890ab'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new metric columns to templates table (using IF NOT EXISTS to avoid conflicts)
    # Note: preview_file_path, token_cost, created_at, updated_at already exist in base migration
    op.execute('ALTER TABLE templates ADD COLUMN IF NOT EXISTS preview_count INTEGER NOT NULL DEFAULT 0')
    op.execute('ALTER TABLE templates ADD COLUMN IF NOT EXISTS preview_to_download_rate FLOAT NOT NULL DEFAULT 0.0')  
    op.execute('ALTER TABLE templates ADD COLUMN IF NOT EXISTS average_generation_time FLOAT')


def downgrade() -> None:
    # Remove only the metric columns added in this migration
    # Note: preview_file_path, token_cost, created_at, updated_at belong to base migration
    op.drop_column('templates', 'preview_count')
    op.drop_column('templates', 'preview_to_download_rate')
    op.drop_column('templates', 'average_generation_time')