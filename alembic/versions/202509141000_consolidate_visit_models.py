"""
Consolidate visit tracking models into unified structure

Revision ID: consolidate_visit_models
Create Date: 2025-09-14 10:00:00
"""

import sqlalchemy as sa
from alembic import op
import json
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'consolidate_visit_models'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create new tables
    op.create_table(
        'document_visits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('device_fingerprint', sa.String(64), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('browser_name', sa.String(100), nullable=True),
        sa.Column('browser_version', sa.String(50), nullable=True),
        sa.Column('os_name', sa.String(100), nullable=True),
        sa.Column('os_version', sa.String(50), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('screen_resolution', sa.String(50), nullable=True),
        sa.Column('referrer', sa.String(500), nullable=True),
        sa.Column('referrer_domain', sa.String(255), nullable=True),
        sa.Column('utm_source', sa.String(100), nullable=True),
        sa.Column('utm_medium', sa.String(100), nullable=True),
        sa.Column('utm_campaign', sa.String(100), nullable=True),
        sa.Column('utm_term', sa.String(100), nullable=True),
        sa.Column('utm_content', sa.String(100), nullable=True),
        sa.Column('country', sa.String(2), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('bounce', sa.Boolean(), default=True),
        sa.Column('bounce_type', sa.String(20), nullable=True),
        sa.Column('time_on_page_seconds', sa.Integer(), default=0),
        sa.Column('active_time_seconds', sa.Integer(), default=0),
        sa.Column('scroll_depth', sa.Integer(), default=0),
        sa.Column('clicks_count', sa.Integer(), default=0),
        sa.Column('session_quality_score', sa.Float(), default=0),
        sa.Column('engagement_depth', sa.Integer(), default=0),
        sa.Column('ab_test_group', sa.String(50), nullable=True),
        sa.Column('ab_test_variant', sa.String(50), nullable=True),
        sa.Column('ab_test_performance', sa.Float(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('last_interaction_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('visit_type', sa.String(20), nullable=False),
        sa.Column('download_completed', sa.Boolean(), default=False),
        sa.Column('time_reading', sa.Integer(), default=0),
        sa.Column('scroll_coverage', sa.Float(), default=0),
        sa.Column('interactions', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'landing_visits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('device_fingerprint', sa.String(64), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('browser_name', sa.String(100), nullable=True),
        sa.Column('browser_version', sa.String(50), nullable=True),
        sa.Column('os_name', sa.String(100), nullable=True),
        sa.Column('os_version', sa.String(50), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('screen_resolution', sa.String(50), nullable=True),
        sa.Column('referrer', sa.String(500), nullable=True),
        sa.Column('referrer_domain', sa.String(255), nullable=True),
        sa.Column('utm_source', sa.String(100), nullable=True),
        sa.Column('utm_medium', sa.String(100), nullable=True),
        sa.Column('utm_campaign', sa.String(100), nullable=True),
        sa.Column('utm_term', sa.String(100), nullable=True),
        sa.Column('utm_content', sa.String(100), nullable=True),
        sa.Column('country', sa.String(2), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('bounce', sa.Boolean(), default=True),
        sa.Column('bounce_type', sa.String(20), nullable=True),
        sa.Column('time_on_page_seconds', sa.Integer(), default=0),
        sa.Column('active_time_seconds', sa.Integer(), default=0),
        sa.Column('scroll_depth', sa.Integer(), default=0),
        sa.Column('clicks_count', sa.Integer(), default=0),
        sa.Column('session_quality_score', sa.Float(), default=0),
        sa.Column('engagement_depth', sa.Integer(), default=0),
        sa.Column('ab_test_group', sa.String(50), nullable=True),
        sa.Column('ab_test_variant', sa.String(50), nullable=True),
        sa.Column('ab_test_performance', sa.Float(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('last_interaction_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('entry_page', sa.String(500), nullable=True),
        sa.Column('exit_page', sa.String(500), nullable=True),
        sa.Column('pages_viewed', sa.JSON(), nullable=True),
        sa.Column('viewed_templates', sa.JSON(), nullable=True),
        sa.Column('searched_terms', sa.JSON(), nullable=True),
        sa.Column('template_interactions', sa.JSON(), nullable=True),
        sa.Column('templates_viewed_count', sa.Integer(), default=0),
        sa.Column('searches_performed', sa.Integer(), default=0),
        sa.Column('form_interactions', sa.JSON(), nullable=True),
        sa.Column('form_completion', sa.Float(), default=0),
        sa.Column('form_abandonment', sa.Boolean(), default=False),
        sa.Column('last_interaction_field', sa.String(100), nullable=True),
        sa.Column('funnel_stage', sa.String(50), nullable=True),
        sa.Column('created_document', sa.Boolean(), default=False),
        sa.Column('registered', sa.Boolean(), default=False),
        sa.Column('downloaded_document', sa.Boolean(), default=False),
        sa.Column('converted_to_paid', sa.Boolean(), default=False),
        sa.Column('conversion_probability', sa.Float(), default=0),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'page_visits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('device_fingerprint', sa.String(64), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('browser_name', sa.String(100), nullable=True),
        sa.Column('browser_version', sa.String(50), nullable=True),
        sa.Column('os_name', sa.String(100), nullable=True),
        sa.Column('os_version', sa.String(50), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('screen_resolution', sa.String(50), nullable=True),
        sa.Column('referrer', sa.String(500), nullable=True),
        sa.Column('referrer_domain', sa.String(255), nullable=True),
        sa.Column('utm_source', sa.String(100), nullable=True),
        sa.Column('utm_medium', sa.String(100), nullable=True),
        sa.Column('utm_campaign', sa.String(100), nullable=True),
        sa.Column('utm_term', sa.String(100), nullable=True),
        sa.Column('utm_content', sa.String(100), nullable=True),
        sa.Column('country', sa.String(2), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('timezone', sa.String(50), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('bounce', sa.Boolean(), default=True),
        sa.Column('bounce_type', sa.String(20), nullable=True),
        sa.Column('time_on_page_seconds', sa.Integer(), default=0),
        sa.Column('active_time_seconds', sa.Integer(), default=0),
        sa.Column('scroll_depth', sa.Integer(), default=0),
        sa.Column('clicks_count', sa.Integer(), default=0),
        sa.Column('session_quality_score', sa.Float(), default=0),
        sa.Column('engagement_depth', sa.Integer(), default=0),
        sa.Column('ab_test_group', sa.String(50), nullable=True),
        sa.Column('ab_test_variant', sa.String(50), nullable=True),
        sa.Column('ab_test_performance', sa.Float(), default=0),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('last_interaction_at', sa.DateTime(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('query_params', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('page_load_time', sa.Integer(), nullable=True),
        sa.Column('dom_interactive_time', sa.Integer(), nullable=True),
        sa.Column('first_paint_time', sa.Integer(), nullable=True),
        sa.Column('navigation_type', sa.String(20), nullable=True),
        sa.Column('was_cached', sa.Boolean(), default=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    for table in ['document_visits', 'landing_visits', 'page_visits']:
        op.create_index(f'{table}_session_id_idx', table, ['session_id'])
        op.create_index(f'{table}_device_fingerprint_idx', table, ['device_fingerprint'])
        op.create_index(f'{table}_referrer_domain_idx', table, ['referrer_domain'])
        op.create_index(f'{table}_utm_source_idx', table, ['utm_source'])
        op.create_index(f'{table}_utm_medium_idx', table, ['utm_medium'])
        op.create_index(f'{table}_utm_campaign_idx', table, ['utm_campaign'])
        op.create_index(f'{table}_country_idx', table, ['country'])
        op.create_index(f'{table}_ab_test_group_idx', table, ['ab_test_group'])
        op.create_index(f'{table}_created_at_idx', table, ['created_at'])

    # Additional specific indexes
    op.create_index('landing_visits_funnel_stage_idx', 'landing_visits', ['funnel_stage'])


def downgrade():
    for table in ['document_visits', 'landing_visits', 'page_visits']:
        op.drop_table(table)