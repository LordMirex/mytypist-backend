"""Add referral system tables"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = '1234567890cd'
down_revision = '1234567890ab'
branch_labels = None
depends_on = None


def upgrade():
    # Create referral_programs table
    op.create_table(
        'referral_programs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('program_code', sa.String(length=50), nullable=False),
        sa.Column('referrer_token_amount', sa.Integer(), nullable=False),
        sa.Column('referee_token_amount', sa.Integer(), nullable=False),
        sa.Column('bonus_multiplier', sa.Float(), nullable=False, default=1.0),
        sa.Column('max_referrals_per_user', sa.Integer(), nullable=True),
        sa.Column('max_total_referrals', sa.Integer(), nullable=True),
        sa.Column('max_total_rewards', sa.Integer(), nullable=True),
        sa.Column('min_referrer_age_days', sa.Integer(), nullable=False, default=0),
        sa.Column('referrer_requires_email', sa.Boolean(), nullable=False, default=True),
        sa.Column('referrer_requires_purchase', sa.Boolean(), nullable=False, default=False),
        sa.Column('total_referrals', sa.Integer(), nullable=False, default=0),
        sa.Column('total_rewards_given', sa.Integer(), nullable=False, default=0),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('starts_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=False),
        sa.Column('conversion_rate', sa.Float(), nullable=False, default=0.0),
        sa.Column('retention_rate', sa.Float(), nullable=False, default=0.0),
        sa.Column('roi', sa.Float(), nullable=False, default=0.0),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_referral_programs_id', 'referral_programs', ['id'])
    op.create_index('ix_referral_programs_program_code', 'referral_programs', ['program_code'], unique=True)

    # Create referral_tracking table
    op.create_table(
        'referral_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('referrer_id', sa.Integer(), nullable=False),
        sa.Column('referee_id', sa.Integer(), nullable=True),
        sa.Column('referral_code', sa.String(length=50), nullable=False),
        sa.Column('referee_email', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='pending'),
        sa.Column('sign_up_date', sa.DateTime(), nullable=True),
        sa.Column('completion_date', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(length=100), nullable=True),
        sa.Column('utm_source', sa.String(length=100), nullable=True),
        sa.Column('utm_medium', sa.String(length=100), nullable=True),
        sa.Column('utm_campaign', sa.String(length=100), nullable=True),
        sa.Column('referrer_reward', sa.Integer(), nullable=True),
        sa.Column('referee_reward', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['program_id'], ['referral_programs.id'], ),
        sa.ForeignKeyConstraint(['referrer_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['referee_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_referral_tracking_id', 'referral_tracking', ['id'])
    op.create_index('ix_referral_tracking_referral_code', 'referral_tracking', ['referral_code'])


def downgrade():
    op.drop_table('referral_tracking')
    op.drop_table('referral_programs')