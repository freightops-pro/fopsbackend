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
down_revision: Union[str, None] = '9ba652cbfdda'
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

    # Create hq_chart_of_accounts table using raw SQL to avoid enum creation issues
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_chart_of_accounts (
            id VARCHAR(36) PRIMARY KEY,
            account_number VARCHAR(10) UNIQUE NOT NULL,
            account_name VARCHAR(255) NOT NULL,
            description TEXT,
            account_type accounttype NOT NULL,
            account_subtype accountsubtype,
            parent_account_id VARCHAR(36) REFERENCES hq_chart_of_accounts(id),
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            is_system BOOLEAN DEFAULT FALSE NOT NULL,
            current_balance NUMERIC(14, 2) DEFAULT 0 NOT NULL,
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL
        )
    """)
    op.create_index('ix_hq_coa_account_type', 'hq_chart_of_accounts', ['account_type'])
    op.create_index('ix_hq_coa_account_number', 'hq_chart_of_accounts', ['account_number'])

    # Create hq_journal_entry table using raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_journal_entry (
            id VARCHAR(36) PRIMARY KEY,
            entry_number VARCHAR(20) UNIQUE NOT NULL,
            reference VARCHAR(100),
            transaction_date TIMESTAMP NOT NULL,
            description TEXT NOT NULL,
            status journalentrystatus DEFAULT 'draft' NOT NULL,
            source_type VARCHAR(50),
            source_id VARCHAR(36),
            tenant_id VARCHAR(36) REFERENCES hq_tenant(id),
            total_debits NUMERIC(14, 2) DEFAULT 0 NOT NULL,
            total_credits NUMERIC(14, 2) DEFAULT 0 NOT NULL,
            created_by_id VARCHAR(36) REFERENCES hq_employee(id),
            posted_by_id VARCHAR(36) REFERENCES hq_employee(id),
            posted_at TIMESTAMP,
            voided_at TIMESTAMP,
            voided_by_id VARCHAR(36) REFERENCES hq_employee(id),
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL
        )
    """)
    op.create_index('ix_hq_je_transaction_date', 'hq_journal_entry', ['transaction_date'])
    op.create_index('ix_hq_je_tenant_id', 'hq_journal_entry', ['tenant_id'])
    op.create_index('ix_hq_je_source', 'hq_journal_entry', ['source_type', 'source_id'])

    # Create hq_general_ledger_entry table using raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_general_ledger_entry (
            id VARCHAR(36) PRIMARY KEY,
            journal_entry_id VARCHAR(36) NOT NULL REFERENCES hq_journal_entry(id),
            debit_account_id VARCHAR(36) REFERENCES hq_chart_of_accounts(id),
            credit_account_id VARCHAR(36) REFERENCES hq_chart_of_accounts(id),
            amount NUMERIC(14, 2) NOT NULL,
            memo TEXT,
            tenant_id VARCHAR(36) REFERENCES hq_tenant(id),
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            CONSTRAINT ck_gle_debit_or_credit CHECK (
                (debit_account_id IS NOT NULL AND credit_account_id IS NULL) OR
                (debit_account_id IS NULL AND credit_account_id IS NOT NULL)
            ),
            CONSTRAINT ck_gle_positive_amount CHECK (amount > 0)
        )
    """)
    op.create_index('ix_hq_gle_journal_entry_id', 'hq_general_ledger_entry', ['journal_entry_id'])
    op.create_index('ix_hq_gle_debit_account', 'hq_general_ledger_entry', ['debit_account_id'])
    op.create_index('ix_hq_gle_credit_account', 'hq_general_ledger_entry', ['credit_account_id'])
    op.create_index('ix_hq_gle_tenant_id', 'hq_general_ledger_entry', ['tenant_id'])

    # Create hq_usage_log table using raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_usage_log (
            id VARCHAR(36) PRIMARY KEY,
            tenant_id VARCHAR(36) NOT NULL REFERENCES hq_tenant(id),
            metric_type usagemetrictype NOT NULL,
            metric_value NUMERIC(14, 4) NOT NULL,
            recorded_at TIMESTAMP DEFAULT NOW() NOT NULL,
            period_start TIMESTAMP,
            period_end TIMESTAMP,
            unit_cost NUMERIC(10, 6),
            total_cost NUMERIC(12, 4),
            ai_metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW() NOT NULL
        )
    """)
    op.create_index('ix_hq_usage_tenant_metric', 'hq_usage_log', ['tenant_id', 'metric_type'])
    op.create_index('ix_hq_usage_recorded_at', 'hq_usage_log', ['recorded_at'])
    op.create_index('ix_hq_usage_period', 'hq_usage_log', ['period_start', 'period_end'])

    # Create hq_recurring_billing table using raw SQL
    # NOTE: FK to hq_customer will be added later after that table is created
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_recurring_billing (
            id VARCHAR(36) PRIMARY KEY,
            tenant_id VARCHAR(36) NOT NULL REFERENCES hq_tenant(id),
            customer_id VARCHAR(36) NOT NULL,
            frequency billingfrequency DEFAULT 'monthly' NOT NULL,
            billing_anchor_day INTEGER DEFAULT 1 NOT NULL,
            base_amount NUMERIC(10, 2) NOT NULL,
            pricing_model VARCHAR(50) DEFAULT 'per_unit' NOT NULL,
            metric_type usagemetrictype,
            unit_price NUMERIC(10, 2),
            add_ons JSONB DEFAULT '[]' NOT NULL,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            next_billing_date TIMESTAMP,
            last_billed_date TIMESTAMP,
            contract_id VARCHAR(36),
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL
        )
    """)
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
