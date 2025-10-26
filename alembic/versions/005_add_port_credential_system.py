"""Add port credential management system

Revision ID: 005_add_port_credential_system
Revises: 004_add_team_messaging
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_port_credential_system'
down_revision = '004_add_team_messaging'
branch_labels = None
depends_on = None


def upgrade():
    """Create port credential system tables"""
    
    # Create ports table
    op.create_table('ports',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('port_code', sa.String(length=10), nullable=False),
        sa.Column('port_name', sa.String(length=255), nullable=False),
        sa.Column('unlocode', sa.String(length=5), nullable=False),
        sa.Column('region', sa.String(length=50), nullable=True),
        sa.Column('state', sa.String(length=2), nullable=True),
        sa.Column('api_endpoint', sa.String(length=500), nullable=False),
        sa.Column('api_version', sa.String(length=20), nullable=True, default='1.0'),
        sa.Column('auth_type', sa.Enum('api_key', 'oauth2', 'basic_auth', 'client_cert', 'jwt', name='portauthtype'), nullable=False),
        sa.Column('services_supported', sa.JSON(), nullable=True),
        sa.Column('rate_limits', sa.JSON(), nullable=True),
        sa.Column('compliance_standards', sa.JSON(), nullable=True),
        sa.Column('documentation_requirements', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('priority', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for ports
    op.create_index(op.f('ix_ports_id'), 'ports', ['id'], unique=False)
    op.create_index(op.f('ix_ports_port_code'), 'ports', ['port_code'], unique=True)
    op.create_index(op.f('ix_ports_unlocode'), 'ports', ['unlocode'], unique=True)
    
    # Create port_credentials table
    op.create_table('port_credentials',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('port_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('encrypted_credentials', sa.Text(), nullable=False),
        sa.Column('credential_type', sa.String(length=50), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_validated', sa.DateTime(), nullable=True),
        sa.Column('validation_status', sa.String(length=20), nullable=True, default='pending'),
        sa.Column('rotation_required', sa.Boolean(), nullable=True, default=False),
        sa.Column('rotation_scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=True, default=0),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['port_id'], ['ports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for port_credentials
    op.create_index('ix_port_credentials_company_port', 'port_credentials', ['company_id', 'port_id'], unique=False)
    
    # Create company_port_addons table
    op.create_table('company_port_addons',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('pricing_model', sa.Enum('pay_per_request', 'unlimited_monthly', name='portaddonpricing'), nullable=False),
        sa.Column('monthly_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('subscription_start', sa.DateTime(), nullable=True),
        sa.Column('subscription_end', sa.DateTime(), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), nullable=True, default=True),
        sa.Column('current_month', sa.String(length=7), nullable=True),
        sa.Column('current_month_requests', sa.Integer(), nullable=True, default=0),
        sa.Column('current_month_cost', sa.Numeric(precision=10, scale=2), nullable=True, default=0),
        sa.Column('auto_optimize', sa.Boolean(), nullable=True, default=False),
        sa.Column('last_optimization_check', sa.DateTime(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('next_billing_date', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique constraint for company_port_addons
    op.create_unique_constraint('uq_company_port_addons_company_id', 'company_port_addons', ['company_id'])
    
    # Create port_api_usage table
    op.create_table('port_api_usage',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('port_code', sa.String(length=10), nullable=False),
        sa.Column('operation', sa.String(length=50), nullable=False),
        sa.Column('operation_cost', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('request_params', sa.JSON(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('billing_month', sa.String(length=7), nullable=False),
        sa.Column('billed', sa.Boolean(), nullable=True, default=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for port_api_usage
    op.create_index(op.f('ix_port_api_usage_id'), 'port_api_usage', ['id'], unique=False)
    op.create_index(op.f('ix_port_api_usage_company_id'), 'port_api_usage', ['company_id'], unique=False)
    op.create_index(op.f('ix_port_api_usage_port_code'), 'port_api_usage', ['port_code'], unique=False)
    op.create_index(op.f('ix_port_api_usage_billing_month'), 'port_api_usage', ['billing_month'], unique=False)
    op.create_index(op.f('ix_port_api_usage_timestamp'), 'port_api_usage', ['timestamp'], unique=False)
    op.create_index('ix_port_api_usage_billing', 'port_api_usage', ['company_id', 'billing_month'], unique=False)
    
    # Create port_audit_logs table
    op.create_table('port_audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('port_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('credential_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('action_status', sa.String(length=20), nullable=False),
        sa.Column('request_data', sa.JSON(), nullable=True),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['credential_id'], ['port_credentials.id'], ),
        sa.ForeignKeyConstraint(['port_id'], ['ports.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for port_audit_logs
    op.create_index(op.f('ix_port_audit_logs_id'), 'port_audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_port_audit_logs_action_type'), 'port_audit_logs', ['action_type'], unique=False)
    op.create_index(op.f('ix_port_audit_logs_created_at'), 'port_audit_logs', ['created_at'], unique=False)
    
    # Create port_health_checks table
    op.create_table('port_health_checks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('port_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=True, default=0),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('failover_active', sa.Boolean(), nullable=True, default=False),
        sa.Column('failover_endpoint', sa.String(length=500), nullable=True),
        sa.Column('checked_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['port_id'], ['ports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for port_health_checks
    op.create_index(op.f('ix_port_health_checks_id'), 'port_health_checks', ['id'], unique=False)
    op.create_index(op.f('ix_port_health_checks_checked_at'), 'port_health_checks', ['checked_at'], unique=False)


def downgrade():
    """Drop port credential system tables"""
    
    # Drop indexes
    op.drop_index(op.f('ix_port_health_checks_checked_at'), table_name='port_health_checks')
    op.drop_index(op.f('ix_port_health_checks_id'), table_name='port_health_checks')
    
    op.drop_index(op.f('ix_port_audit_logs_created_at'), table_name='port_audit_logs')
    op.drop_index(op.f('ix_port_audit_logs_action_type'), table_name='port_audit_logs')
    op.drop_index(op.f('ix_port_audit_logs_id'), table_name='port_audit_logs')
    
    op.drop_index('ix_port_api_usage_billing', table_name='port_api_usage')
    op.drop_index(op.f('ix_port_api_usage_timestamp'), table_name='port_api_usage')
    op.drop_index(op.f('ix_port_api_usage_billing_month'), table_name='port_api_usage')
    op.drop_index(op.f('ix_port_api_usage_port_code'), table_name='port_api_usage')
    op.drop_index(op.f('ix_port_api_usage_company_id'), table_name='port_api_usage')
    op.drop_index(op.f('ix_port_api_usage_id'), table_name='port_api_usage')
    
    op.drop_index(op.f('ix_ports_unlocode'), table_name='ports')
    op.drop_index(op.f('ix_ports_port_code'), table_name='ports')
    op.drop_index(op.f('ix_ports_id'), table_name='ports')
    
    # Drop tables
    op.drop_table('port_health_checks')
    op.drop_table('port_audit_logs')
    op.drop_table('port_api_usage')
    op.drop_table('company_port_addons')
    op.drop_index('ix_port_credentials_company_port', table_name='port_credentials')
    op.drop_table('port_credentials')
    op.drop_table('ports')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS portaddonpricing')
    op.execute('DROP TYPE IF EXISTS portauthtype')




