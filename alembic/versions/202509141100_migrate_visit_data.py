"""
Data migration for visit model consolidation

Revision ID: migrate_visit_data
Create Date: 2025-09-14 11:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
import json
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'migrate_visit_data'
down_revision = 'consolidate_visit_models'
branch_labels = None
depends_on = None


def upgrade():
    # This migration is designed for data migration from legacy visit tables
    # In a fresh database setup, there's no legacy data to migrate
    # So this migration becomes a no-op for new installations
    pass


def downgrade():
    # No data to rollback in a fresh installation
    pass