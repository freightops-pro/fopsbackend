"""Add HQ Admin Portal tables.

Revision ID: 20251129_000013
Revises: e9f31e598fb6
Create Date: 2025-11-29

"""
from alembic import op
import sqlalchemy as sa
from passlib.context import CryptContext
import uuid

# revision identifiers, used by Alembic.
revision = '20251129_000013'
down_revision = '20251129_000012'
branch_labels = None
depends_on = None

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    # Create HQ Employee table
    op.create_table(
        'hq_employee',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('employee_number', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('role', sa.Enum('SUPER_ADMIN', 'ADMIN', 'HR_MANAGER', 'SALES_MANAGER', 'ACCOUNTANT', 'SUPPORT', name='hqrole'), nullable=False),
        sa.Column('department', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('must_change_password', sa.Boolean(), nullable=False, default=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_employee_email'), 'hq_employee', ['email'], unique=True)
    op.create_index(op.f('ix_hq_employee_employee_number'), 'hq_employee', ['employee_number'], unique=True)

    # Create HQ Tenant table
    op.create_table(
        'hq_tenant',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('active', 'trial', 'suspended', 'cancelled', name='tenantstatus'), nullable=False),
        sa.Column('subscription_tier', sa.Enum('starter', 'professional', 'enterprise', 'custom', name='subscriptiontier'), nullable=False),
        sa.Column('monthly_rate', sa.Numeric(10, 2), nullable=True),
        sa.Column('billing_email', sa.String(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('subscription_started_at', sa.DateTime(), nullable=True),
        sa.Column('current_period_ends_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_sales_rep_id', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.ForeignKeyConstraint(['assigned_sales_rep_id'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_tenant_company_id'), 'hq_tenant', ['company_id'], unique=True)
    op.create_index(op.f('ix_hq_tenant_stripe_customer_id'), 'hq_tenant', ['stripe_customer_id'], unique=True)

    # Create HQ Contract table
    op.create_table(
        'hq_contract',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('contract_number', sa.String(), nullable=False),
        sa.Column('contract_type', sa.Enum('standard', 'enterprise', 'custom', 'pilot', name='contracttype'), nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending_approval', 'active', 'expired', 'terminated', 'renewed', name='contractstatus'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('monthly_value', sa.Numeric(10, 2), nullable=False),
        sa.Column('annual_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('setup_fee', sa.Numeric(10, 2), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('auto_renew', sa.String(), nullable=True),
        sa.Column('notice_period_days', sa.String(), nullable=True),
        sa.Column('custom_terms', sa.Text(), nullable=True),
        sa.Column('signed_by_customer', sa.String(), nullable=True),
        sa.Column('signed_by_hq', sa.String(), nullable=True),
        sa.Column('signed_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_id', sa.String(), nullable=True),
        sa.Column('approved_by_id', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['hq_tenant.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['hq_employee.id'], ),
        sa.ForeignKeyConstraint(['approved_by_id'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_contract_tenant_id'), 'hq_contract', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_hq_contract_contract_number'), 'hq_contract', ['contract_number'], unique=True)

    # Create HQ Quote table
    op.create_table(
        'hq_quote',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=True),
        sa.Column('quote_number', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('draft', 'sent', 'viewed', 'accepted', 'rejected', 'expired', name='quotestatus'), nullable=False),
        sa.Column('contact_name', sa.String(), nullable=True),
        sa.Column('contact_email', sa.String(), nullable=True),
        sa.Column('contact_company', sa.String(), nullable=True),
        sa.Column('contact_phone', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tier', sa.String(), nullable=False),
        sa.Column('base_monthly_rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('discount_percent', sa.Numeric(5, 2), nullable=True),
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('final_monthly_rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('setup_fee', sa.Numeric(10, 2), nullable=True),
        sa.Column('addons', sa.Text(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('viewed_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['hq_tenant.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_quote_tenant_id'), 'hq_quote', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_hq_quote_quote_number'), 'hq_quote', ['quote_number'], unique=True)

    # Create HQ Credit table
    op.create_table(
        'hq_credit',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('credit_type', sa.Enum('promotional', 'service_issue', 'billing_adjustment', 'goodwill', 'referral', name='credittype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'applied', 'expired', name='creditstatus'), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('remaining_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('requested_by_id', sa.String(), nullable=False),
        sa.Column('approved_by_id', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_by_id', sa.String(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('applied_to_invoice_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['hq_tenant.id'], ),
        sa.ForeignKeyConstraint(['requested_by_id'], ['hq_employee.id'], ),
        sa.ForeignKeyConstraint(['approved_by_id'], ['hq_employee.id'], ),
        sa.ForeignKeyConstraint(['rejected_by_id'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_credit_tenant_id'), 'hq_credit', ['tenant_id'], unique=False)

    # Create HQ Payout table
    op.create_table(
        'hq_payout',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'cancelled', name='payoutstatus'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False),
        sa.Column('stripe_payout_id', sa.String(), nullable=True),
        sa.Column('stripe_transfer_id', sa.String(), nullable=True),
        sa.Column('stripe_destination_account', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=True),
        sa.Column('period_end', sa.DateTime(), nullable=True),
        sa.Column('initiated_by_id', sa.String(), nullable=True),
        sa.Column('initiated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['hq_tenant.id'], ),
        sa.ForeignKeyConstraint(['initiated_by_id'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_payout_tenant_id'), 'hq_payout', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_hq_payout_stripe_payout_id'), 'hq_payout', ['stripe_payout_id'], unique=True)

    # Create HQ System Module table
    op.create_table(
        'hq_system_module',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('active', 'maintenance', 'disabled', name='modulestatus'), nullable=False),
        sa.Column('maintenance_message', sa.Text(), nullable=True),
        sa.Column('maintenance_end_time', sa.DateTime(), nullable=True),
        sa.Column('last_updated_by_id', sa.String(), nullable=True),
        sa.Column('last_updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['last_updated_by_id'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_system_module_key'), 'hq_system_module', ['key'], unique=True)

    # Seed super user: Rene Carbonell, admin@freightopspro.com, Catalina$2023, employee #001
    hashed_password = pwd_context.hash("Catalina$2023")
    super_user_id = str(uuid.uuid4())

    op.execute(
        f"""
        INSERT INTO hq_employee (id, employee_number, email, hashed_password, first_name, last_name, role, is_active, must_change_password)
        VALUES ('{super_user_id}', '001', 'admin@freightopspro.com', '{hashed_password}', 'Rene', 'Carbonell', 'SUPER_ADMIN', true, false)
        """
    )

    # Seed default system modules
    modules = [
        ('dashboard', 'Dashboard', 'Main HQ dashboard with metrics and overview'),
        ('tenants', 'Tenant Management', 'Manage customer tenants and subscriptions'),
        ('hr', 'Human Resources', 'HQ employee management'),
        ('sales', 'Sales', 'Contracts, quotes, and credits management'),
        ('accounting', 'Accounting', 'Platform-level accounting and transactions'),
        ('banking', 'Banking', 'Stripe Connect account management'),
        ('wallet', 'Wallet & Payouts', 'Tenant payouts and wallet balances'),
    ]

    for key, name, description in modules:
        module_id = str(uuid.uuid4())
        op.execute(
            f"""
            INSERT INTO hq_system_module (id, key, name, description, status)
            VALUES ('{module_id}', '{key}', '{name}', '{description}', 'active')
            """
        )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_hq_system_module_key'), table_name='hq_system_module')
    op.drop_table('hq_system_module')

    op.drop_index(op.f('ix_hq_payout_stripe_payout_id'), table_name='hq_payout')
    op.drop_index(op.f('ix_hq_payout_tenant_id'), table_name='hq_payout')
    op.drop_table('hq_payout')

    op.drop_index(op.f('ix_hq_credit_tenant_id'), table_name='hq_credit')
    op.drop_table('hq_credit')

    op.drop_index(op.f('ix_hq_quote_quote_number'), table_name='hq_quote')
    op.drop_index(op.f('ix_hq_quote_tenant_id'), table_name='hq_quote')
    op.drop_table('hq_quote')

    op.drop_index(op.f('ix_hq_contract_contract_number'), table_name='hq_contract')
    op.drop_index(op.f('ix_hq_contract_tenant_id'), table_name='hq_contract')
    op.drop_table('hq_contract')

    op.drop_index(op.f('ix_hq_tenant_stripe_customer_id'), table_name='hq_tenant')
    op.drop_index(op.f('ix_hq_tenant_company_id'), table_name='hq_tenant')
    op.drop_table('hq_tenant')

    op.drop_index(op.f('ix_hq_employee_employee_number'), table_name='hq_employee')
    op.drop_index(op.f('ix_hq_employee_email'), table_name='hq_employee')
    op.drop_table('hq_employee')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS modulestatus')
    op.execute('DROP TYPE IF EXISTS payoutstatus')
    op.execute('DROP TYPE IF EXISTS creditstatus')
    op.execute('DROP TYPE IF EXISTS credittype')
    op.execute('DROP TYPE IF EXISTS quotestatus')
    op.execute('DROP TYPE IF EXISTS contractstatus')
    op.execute('DROP TYPE IF EXISTS contracttype')
    op.execute('DROP TYPE IF EXISTS subscriptiontier')
    op.execute('DROP TYPE IF EXISTS tenantstatus')
    op.execute('DROP TYPE IF EXISTS hqrole')
