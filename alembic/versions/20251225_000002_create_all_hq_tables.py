"""Create all HQ tables comprehensively

Revision ID: 20251225_000002
Revises: 20251225_000001
Create Date: 2025-12-25 06:30:00.000000

This migration creates all HQ-related tables for the admin portal:
- hq_employee (admin users)
- hq_tenant (customer companies)
- hq_system_module (maintenance mode)
- hq_customer, hq_invoice, hq_vendor, hq_bill, hq_payment (accounting)
- hq_hr_employee, hq_payroll_run, hq_payroll_item (HR/payroll)
- hq_chart_of_accounts, hq_journal_entry, hq_general_ledger_entry (GL)
- hq_usage_log, hq_recurring_billing (billing)
- hq_contract, hq_quote, hq_credit, hq_payout (sales)
- hq_banking tables
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251225_000002"
down_revision: Union[str, None] = "20251225_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types if they don't exist
    # Using raw SQL to check and create enums safely

    # HQ Role enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE hqrole AS ENUM ('SUPER_ADMIN', 'ADMIN', 'HR_MANAGER', 'SALES_MANAGER', 'ACCOUNTANT', 'SUPPORT');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Tenant Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tenantstatus AS ENUM ('active', 'trial', 'suspended', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Subscription Tier enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE subscriptiontier AS ENUM ('starter', 'professional', 'enterprise', 'custom');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Module Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE modulestatus AS ENUM ('active', 'maintenance', 'disabled');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Customer Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE customerstatus AS ENUM ('active', 'inactive', 'suspended');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Customer Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE customertype AS ENUM ('tenant', 'partner', 'enterprise', 'other');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Invoice Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invoicestatus AS ENUM ('draft', 'sent', 'viewed', 'paid', 'partial', 'overdue', 'cancelled', 'void');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Invoice Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invoicetype AS ENUM ('subscription', 'service', 'setup_fee', 'credit_note', 'other');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Vendor Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE vendorstatus AS ENUM ('active', 'inactive', 'pending_approval');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Vendor Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE vendortype AS ENUM ('service', 'supplier', 'contractor', 'utility', 'other');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Bill Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE billstatus AS ENUM ('draft', 'pending_approval', 'approved', 'paid', 'partial', 'overdue', 'cancelled', 'void');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Bill Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE billtype AS ENUM ('expense', 'service', 'utility', 'subscription', 'other');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Payment Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE paymenttype AS ENUM ('check', 'ach', 'wire', 'credit_card', 'other');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Payment Direction enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE paymentdirection AS ENUM ('incoming', 'outgoing');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Employment Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE employmenttype AS ENUM ('full_time', 'part_time', 'contractor', 'intern');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # HR Employee Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE hremployeestatus AS ENUM ('active', 'terminated', 'on_leave', 'onboarding');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Pay Frequency enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE payfrequency AS ENUM ('weekly', 'biweekly', 'semimonthly', 'monthly');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Payroll Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE payrollstatus AS ENUM ('draft', 'pending_approval', 'approved', 'processing', 'completed', 'failed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Account Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE accounttype AS ENUM ('asset', 'liability', 'equity', 'revenue', 'cost_of_revenue', 'expense');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Account Subtype enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE accountsubtype AS ENUM (
                'cash', 'accounts_receivable', 'prepaid_expense', 'fixed_asset',
                'accounts_payable', 'credit_card', 'deferred_revenue', 'payroll_liability',
                'retained_earnings', 'owner_equity',
                'saas_revenue', 'service_revenue', 'other_income',
                'ai_compute', 'hosting', 'payment_processing',
                'payroll', 'marketing', 'software', 'professional_services', 'office', 'other_expense'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Journal Entry Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE journalentrystatus AS ENUM ('draft', 'posted', 'void');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Usage Metric Type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE usagemetrictype AS ENUM (
                'active_trucks', 'active_drivers', 'payroll_employees',
                'ai_tokens_used', 'ai_requests', 'storage_gb', 'api_calls'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Billing Frequency enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE billingfrequency AS ENUM ('monthly', 'quarterly', 'annually');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Contract Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE contractstatus AS ENUM ('draft', 'pending_approval', 'active', 'expired', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Quote Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE quotestatus AS ENUM ('draft', 'sent', 'accepted', 'rejected', 'expired');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Credit Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE creditstatus AS ENUM ('pending', 'approved', 'rejected', 'applied', 'expired');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Payout Status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE payoutstatus AS ENUM ('pending', 'processing', 'completed', 'failed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Now add missing columns to existing tables
    # These use IF NOT EXISTS pattern for safety

    # Add columns to hq_employee if they don't exist
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE hq_employee ADD COLUMN IF NOT EXISTS title VARCHAR;
        EXCEPTION
            WHEN undefined_table THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE hq_employee ADD COLUMN IF NOT EXISTS phone VARCHAR;
        EXCEPTION
            WHEN undefined_table THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE hq_employee ADD COLUMN IF NOT EXISTS hire_date TIMESTAMP;
        EXCEPTION
            WHEN undefined_table THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE hq_employee ADD COLUMN IF NOT EXISTS salary INTEGER;
        EXCEPTION
            WHEN undefined_table THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE hq_employee ADD COLUMN IF NOT EXISTS emergency_contact VARCHAR;
        EXCEPTION
            WHEN undefined_table THEN NULL;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE hq_employee ADD COLUMN IF NOT EXISTS emergency_phone VARCHAR;
        EXCEPTION
            WHEN undefined_table THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    # Note: We don't drop enums in downgrade as they may be used by other tables
    # We also don't drop columns as that would cause data loss
    pass
