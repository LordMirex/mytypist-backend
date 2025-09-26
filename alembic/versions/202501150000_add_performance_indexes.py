"""Add performance indexes

Revision ID: 202501150000
Revises: 7a651ed06d16
Create Date: 2025-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '202501150000'
down_revision = '7a651ed06d16'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for frequently queried columns"""

    # Document model indexes
    op.create_index('ix_documents_user_id_status', 'documents', ['user_id', 'status'])
    op.create_index('ix_documents_template_id', 'documents', ['template_id'])
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])
    op.create_index('ix_documents_access_level', 'documents', ['access_level'])

    # Template model indexes
    op.create_index('ix_templates_category', 'templates', ['category'])
    op.create_index('ix_templates_is_active', 'templates', ['is_active'])
    op.create_index('ix_templates_created_at', 'templates', ['created_at'])
    op.create_index('ix_templates_cluster_id', 'templates', ['cluster_id'])

    # User model indexes
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_status', 'users', ['status'])
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_users_created_at', 'users', ['created_at'])

    # Payment model indexes
    op.create_index('ix_payments_user_id_status', 'payments', ['user_id', 'status'])
    op.create_index('ix_payments_created_at', 'payments', ['created_at'])
    op.create_index('ix_payments_transaction_id', 'payments', ['transaction_id'])

    # Token model indexes
    op.create_index('ix_user_tokens_user_id_type', 'user_tokens', ['user_id', 'transaction_type'])
    op.create_index('ix_user_tokens_created_at', 'user_tokens', ['created_at'])

    # Support ticket indexes
    op.create_index('ix_support_tickets_user_id_status', 'support_tickets', ['user_id', 'status'])
    op.create_index('ix_support_tickets_assigned_to', 'support_tickets', ['assigned_to'])
    op.create_index('ix_support_tickets_created_at', 'support_tickets', ['created_at'])

    # Template category indexes
    op.create_index('ix_template_categories_slug', 'template_categories', ['slug'])
    op.create_index('ix_template_categories_is_active', 'template_categories', ['is_active'])

    # Placeholder indexes
    op.create_index('ix_placeholders_template_id', 'placeholders', ['template_id'])
    op.create_index('ix_placeholders_name', 'placeholders', ['name'])

    # Audit log indexes
    op.create_index('ix_audit_logs_user_id_timestamp', 'audit_logs', ['user_id', 'timestamp'])
    op.create_index('ix_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])

    # Page visit indexes
    op.create_index('ix_page_visits_session_id', 'page_visits', ['session_id'])
    op.create_index('ix_page_visits_created_at', 'page_visits', ['created_at'])
    op.create_index('ix_page_visits_user_id_created_at', 'page_visits', ['user_id', 'created_at'])


def downgrade():
    """Remove performance indexes"""

    # Document model indexes
    op.drop_index('ix_documents_user_id_status', 'documents')
    op.drop_index('ix_documents_template_id', 'documents')
    op.drop_index('ix_documents_created_at', 'documents')
    op.drop_index('ix_documents_access_level', 'documents')

    # Template model indexes
    op.drop_index('ix_templates_category', 'templates')
    op.drop_index('ix_templates_is_active', 'templates')
    op.drop_index('ix_templates_created_at', 'templates')
    op.drop_index('ix_templates_cluster_id', 'templates')

    # User model indexes
    op.drop_index('ix_users_email', 'users')
    op.drop_index('ix_users_status', 'users')
    op.drop_index('ix_users_role', 'users')
    op.drop_index('ix_users_created_at', 'users')

    # Payment model indexes
    op.drop_index('ix_payments_user_id_status', 'payments')
    op.drop_index('ix_payments_created_at', 'payments')
    op.drop_index('ix_payments_transaction_id', 'payments')

    # Token model indexes
    op.drop_index('ix_user_tokens_user_id_type', 'user_tokens')
    op.drop_index('ix_user_tokens_created_at', 'user_tokens')

    # Support ticket indexes
    op.drop_index('ix_support_tickets_user_id_status', 'support_tickets')
    op.drop_index('ix_support_tickets_assigned_to', 'support_tickets')
    op.drop_index('ix_support_tickets_created_at', 'support_tickets')

    # Template category indexes
    op.drop_index('ix_template_categories_slug', 'template_categories')
    op.drop_index('ix_template_categories_is_active', 'template_categories')

    # Placeholder indexes
    op.drop_index('ix_placeholders_template_id', 'placeholders')
    op.drop_index('ix_placeholders_name', 'placeholders')

    # Audit log indexes
    op.drop_index('ix_audit_logs_user_id_timestamp', 'audit_logs')
    op.drop_index('ix_audit_logs_event_type', 'audit_logs')
    op.drop_index('ix_audit_logs_timestamp', 'audit_logs')

    # Page visit indexes
    op.drop_index('ix_page_visits_session_id', 'page_visits')
    op.drop_index('ix_page_visits_created_at', 'page_visits')
    op.drop_index('ix_page_visits_user_id_created_at', 'page_visits')
