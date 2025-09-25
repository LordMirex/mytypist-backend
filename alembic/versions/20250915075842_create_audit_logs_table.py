"""create_audit_logs_table

Revision ID: 20250915075842
Revises: d1f848efafdf
Create Date: 2025-09-15 07:58:42.514427

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250915075842'
down_revision = 'd1f848efafdf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_logs table"""
    # Create the audit_logs table with VARCHAR columns instead of enums
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        
        # Event information
        sa.Column('event_type', sa.String(50), nullable=False, index=True),
        sa.Column('event_level', sa.String(20), nullable=False, server_default="'info'"),
        sa.Column('event_message', sa.Text(), nullable=False),
        sa.Column('event_details', sa.JSON(), nullable=True),
        
        # User and session information
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        
        # Request information
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_method', sa.String(10), nullable=True),
        sa.Column('request_path', sa.String(500), nullable=True),
        sa.Column('request_params', sa.JSON(), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        
        # Resource information
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('resource_name', sa.String(255), nullable=True),
        
        # Geographic information
        sa.Column('country', sa.String(100), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('latitude', sa.String(20), nullable=True),
        sa.Column('longitude', sa.String(20), nullable=True),
        
        # Compliance and security
        sa.Column('gdpr_relevant', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pii_accessed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sensitive_operation', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('requires_retention', sa.Boolean(), nullable=False, server_default='true'),
        
        # Risk assessment
        sa.Column('risk_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('anomaly_detected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('automated_response', sa.String(100), nullable=True),
        
        # Processing information
        sa.Column('processing_time', sa.Float(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('environment', sa.String(20), nullable=False, server_default="'development'"),
        sa.Column('service_version', sa.String(20), nullable=True),
        sa.Column('correlation_id', sa.String(100), nullable=True),
        
        # Timestamps
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def downgrade() -> None:
    """Drop audit_logs table"""
    op.drop_table('audit_logs')
