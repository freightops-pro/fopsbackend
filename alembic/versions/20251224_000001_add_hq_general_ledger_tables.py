"""Add HQ General Ledger tables

Revision ID: 20251224_000001
Revises: 20251223_000001_add_security_fields
Create Date: 2024-12-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251224_000001'
down_revision: Union[str, None] = '20251223_000001_add_security_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create account_type enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'accounttype') THEN
                CREATE TYPE accounttype AS ENUM (
                    'asset', 'liability', 'equity', 'revenue', 'cost_of_revenue', 'expense'
                );
            END IF;
        END $$;
    """)

    # Create account_subtype enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'accountsubtype') THEN
                CREATE TYPE accountsubtype AS ENUM (
                    'cash', 'accounts_receivable', 'prepaid_expense', 'fixed_asset',
                    'accounts_payable', 'credit_card', 'deferred_revenue', 'payroll_liability',
                    'retained_earnings', 'owner_equity',
                    'saas_revenue', 'service_revenue', 'other_income',
                    'ai_compute', 'hosting', 'payment_processing',
                    'payroll', 'marketing', 'software', 'professional_services', 'office', 'other_expense'
                );
            END IF;
        END $$;
    """)

    # Create journal_entry_status enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'journalentrystatus') THEN
                CREATE TYPE journalentrystatus AS ENUM ('draft', 'posted', 'void');
            END IF;
        END $$;
    """)

    # Create usage_metric_type enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'usagemetrictype') THEN
                CREATE TYPE usagemetrictype AS ENUM (
                    'active_trucks', 'active_drivers', 'payroll_employees',
                    'ai_tokens_used', 'ai_requests', 'storage_gb', 'api_calls'
                );
            END IF;
        END $$;
    """)

    # Create billing_frequency enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'billingfrequency') THEN
                CREATE TYPE billingfrequency AS ENUM ('monthly', 'quarterly', 'annually');
            END IF;
        END $$;
    """)

    # Create hq_chart_of_accounts table
    op.create_table(
        'hq_chart_of_accounts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_number', sa.String(10), unique=True, nullable=False),
        sa.Column('account_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('account_type', sa.Enum('asset', 'liability', 'equity', 'revenue', 'cost_of_revenue', 'expense', name='accounttype', create_type=False), nullable=False),
        sa.Column('account_subtype', sa.Enum('cash', 'accounts_receivable', 'prepaid_expense', 'fixed_asset', 'accounts_payable', 'credit_card', 'deferred_revenue', 'payroll_liability', 'retained_earnings', 'owner_equity', 'saas_revenue', 'service_revenue', 'other_income', 'ai_compute', 'hosting', 'payment_processing', 'payroll', 'marketing', 'software', 'professional_services', 'office', 'other_expense', name='accountsubtype', create_type=False), nullable=True),
        sa.Column('parent_account_id', sa.String(36), sa.ForeignKey('hq_chart_of_accounts.id'), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('is_system', sa.Boolean, default=False, nullable=False),
        sa.Column('current_balance', sa.Numeric(14, 2), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hq_coa_account_type', 'hq_chart_of_accounts', ['account_type'])
    op.create_index('ix_hq_coa_account_number', 'hq_chart_of_accounts', ['account_number'])

    # Create hq_journal_entry table
    op.create_table(
        'hq_journal_entry',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('entry_number', sa.String(20), unique=True, nullable=False),
        sa.Column('reference', sa.String(100), nullable=True),
        sa.Column('transaction_date', sa.DateTime, nullable=False),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('status', sa.Enum('draft', 'posted', 'void', name='journalentrystatus', create_type=False), default='draft', nullable=False),
        sa.Column('source_type', sa.String(50), nullable=True),
        sa.Column('source_id', sa.String(36), nullable=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('hq_tenant.id'), nullable=True),
        sa.Column('total_debits', sa.Numeric(14, 2), default=0, nullable=False),
        sa.Column('total_credits', sa.Numeric(14, 2), default=0, nullable=False),
        sa.Column('created_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('posted_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('posted_at', sa.DateTime, nullable=True),
        sa.Column('voided_at', sa.DateTime, nullable=True),
        sa.Column('voided_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hq_je_transaction_date', 'hq_journal_entry', ['transaction_date'])
    op.create_index('ix_hq_je_tenant_id', 'hq_journal_entry', ['tenant_id'])
    op.create_index('ix_hq_je_source', 'hq_journal_entry', ['source_type', 'source_id'])

    # Create hq_general_ledger_entry table
    op.create_table(
        'hq_general_ledger_entry',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('journal_entry_id', sa.String(36), sa.ForeignKey('hq_journal_entry.id'), nullable=False),
        sa.Column('debit_account_id', sa.String(36), sa.ForeignKey('hq_chart_of_accounts.id'), nullable=True),
        sa.Column('credit_account_id', sa.String(36), sa.ForeignKey('hq_chart_of_accounts.id'), nullable=True),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('memo', sa.Text, nullable=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('hq_tenant.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            '(debit_account_id IS NOT NULL AND credit_account_id IS NULL) OR '
            '(debit_account_id IS NULL AND credit_account_id IS NOT NULL)',
            name='ck_gle_debit_or_credit'
        ),
        sa.CheckConstraint('amount > 0', name='ck_gle_positive_amount'),
    )
    op.create_index('ix_hq_gle_journal_entry_id', 'hq_general_ledger_entry', ['journal_entry_id'])
    op.create_index('ix_hq_gle_debit_account', 'hq_general_ledger_entry', ['debit_account_id'])
    op.create_index('ix_hq_gle_credit_account', 'hq_general_ledger_entry', ['credit_account_id'])
    op.create_index('ix_hq_gle_tenant_id', 'hq_general_ledger_entry', ['tenant_id'])

    # Create hq_usage_log table
    op.create_table(
        'hq_usage_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('hq_tenant.id'), nullable=False),
        sa.Column('metric_type', sa.Enum('active_trucks', 'active_drivers', 'payroll_employees', 'ai_tokens_used', 'ai_requests', 'storage_gb', 'api_calls', name='usagemetrictype', create_type=False), nullable=False),
        sa.Column('metric_value', sa.Numeric(14, 4), nullable=False),
        sa.Column('recorded_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('period_start', sa.DateTime, nullable=True),
        sa.Column('period_end', sa.DateTime, nullable=True),
        sa.Column('unit_cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('total_cost', sa.Numeric(12, 4), nullable=True),
        sa.Column('ai_metadata', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hq_usage_tenant_metric', 'hq_usage_log', ['tenant_id', 'metric_type'])
    op.create_index('ix_hq_usage_recorded_at', 'hq_usage_log', ['recorded_at'])
    op.create_index('ix_hq_usage_period', 'hq_usage_log', ['period_start', 'period_end'])

    # Create hq_recurring_billing table
    op.create_table(
        'hq_recurring_billing',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), sa.ForeignKey('hq_tenant.id'), nullable=False),
        sa.Column('customer_id', sa.String(36), sa.ForeignKey('hq_customer.id'), nullable=False),
        sa.Column('frequency', sa.Enum('monthly', 'quarterly', 'annually', name='billingfrequency', create_type=False), default='monthly', nullable=False),
        sa.Column('billing_anchor_day', sa.Integer, default=1, nullable=False),
        sa.Column('base_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('pricing_model', sa.String(50), default='per_unit', nullable=False),
        sa.Column('metric_type', sa.Enum('active_trucks', 'active_drivers', 'payroll_employees', 'ai_tokens_used', 'ai_requests', 'storage_gb', 'api_calls', name='usagemetrictype', create_type=False), nullable=True),
        sa.Column('unit_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('add_ons', sa.JSON, default=list, nullable=False),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('next_billing_date', sa.DateTime, nullable=True),
        sa.Column('last_billed_date', sa.DateTime, nullable=True),
        sa.Column('contract_id', sa.String(36), sa.ForeignKey('hq_contract.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hq_recurring_tenant', 'hq_recurring_billing', ['tenant_id'])
    op.create_index('ix_hq_recurring_next_billing', 'hq_recurring_billing', ['next_billing_date'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_hq_recurring_next_billing', 'hq_recurring_billing')
    op.drop_index('ix_hq_recurring_tenant', 'hq_recurring_billing')
    op.drop_table('hq_recurring_billing')

    op.drop_index('ix_hq_usage_period', 'hq_usage_log')
    op.drop_index('ix_hq_usage_recorded_at', 'hq_usage_log')
    op.drop_index('ix_hq_usage_tenant_metric', 'hq_usage_log')
    op.drop_table('hq_usage_log')

    op.drop_index('ix_hq_gle_tenant_id', 'hq_general_ledger_entry')
    op.drop_index('ix_hq_gle_credit_account', 'hq_general_ledger_entry')
    op.drop_index('ix_hq_gle_debit_account', 'hq_general_ledger_entry')
    op.drop_index('ix_hq_gle_journal_entry_id', 'hq_general_ledger_entry')
    op.drop_table('hq_general_ledger_entry')

    op.drop_index('ix_hq_je_source', 'hq_journal_entry')
    op.drop_index('ix_hq_je_tenant_id', 'hq_journal_entry')
    op.drop_index('ix_hq_je_transaction_date', 'hq_journal_entry')
    op.drop_table('hq_journal_entry')

    op.drop_index('ix_hq_coa_account_number', 'hq_chart_of_accounts')
    op.drop_index('ix_hq_coa_account_type', 'hq_chart_of_accounts')
    op.drop_table('hq_chart_of_accounts')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS billingfrequency")
    op.execute("DROP TYPE IF EXISTS usagemetrictype")
    op.execute("DROP TYPE IF EXISTS journalentrystatus")
    op.execute("DROP TYPE IF EXISTS accountsubtype")
    op.execute("DROP TYPE IF EXISTS accounttype")
