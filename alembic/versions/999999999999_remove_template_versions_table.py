"""remove template versions table

Revision ID: 999999999999
Revises: 1234567890ef
Create Date: 2024-09-12 14:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '999999999999'
down_revision: Union[str, None] = '1234567890ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the template_versions table if it exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'template_versions' in inspector.get_table_names():
        op.drop_table('template_versions')


def downgrade() -> None:
    # Only recreate if using PostgreSQL (skip for SQLite)
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.create_table('template_versions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('template_id', sa.Integer(), nullable=False),
            sa.Column('version', sa.String(length=20), nullable=False),
            sa.Column('changes', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('created_by', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
            sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ),
            sa.PrimaryKeyConstraint('id')
        )