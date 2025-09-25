"""merge_heads

Revision ID: d1f848efafdf
Revises: migrate_visit_data, 7a651ed06d16
Create Date: 2025-09-15 07:03:39.523086

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1f848efafdf'
down_revision = ('migrate_visit_data', '7a651ed06d16')
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade database schema"""
    pass


def downgrade() -> None:
    """Downgrade database schema"""
    pass
