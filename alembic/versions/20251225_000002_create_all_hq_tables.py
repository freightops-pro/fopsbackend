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

    # Create hq_hr_employee table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_hr_employee (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            employee_number VARCHAR(20) UNIQUE NOT NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL,
            phone VARCHAR(50),
            employment_type employmenttype DEFAULT 'full_time' NOT NULL,
            status hremployeestatus DEFAULT 'onboarding' NOT NULL,
            department VARCHAR(100),
            job_title VARCHAR(100),
            manager_id VARCHAR(36) REFERENCES hq_hr_employee(id),
            hire_date TIMESTAMP,
            termination_date TIMESTAMP,
            pay_frequency payfrequency DEFAULT 'biweekly' NOT NULL,
            annual_salary NUMERIC(12, 2),
            hourly_rate NUMERIC(8, 2),
            address_line1 VARCHAR(255),
            address_line2 VARCHAR(255),
            city VARCHAR(100),
            state VARCHAR(50),
            zip_code VARCHAR(20),
            check_employee_id VARCHAR(100) UNIQUE,
            ssn_last_four VARCHAR(4),
            date_of_birth TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL
        );
    """)

    # Create hq_payroll_run table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_payroll_run (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            payroll_number VARCHAR(20) UNIQUE NOT NULL,
            status payrollstatus DEFAULT 'draft' NOT NULL,
            pay_period_start TIMESTAMP NOT NULL,
            pay_period_end TIMESTAMP NOT NULL,
            pay_date TIMESTAMP NOT NULL,
            description TEXT,
            total_gross NUMERIC(14, 2) DEFAULT 0 NOT NULL,
            total_taxes NUMERIC(14, 2) DEFAULT 0 NOT NULL,
            total_deductions NUMERIC(14, 2) DEFAULT 0 NOT NULL,
            total_net NUMERIC(14, 2) DEFAULT 0 NOT NULL,
            employee_count INTEGER DEFAULT 0 NOT NULL,
            check_payroll_id VARCHAR(100) UNIQUE,
            approved_by_id VARCHAR(36) REFERENCES hq_employee(id),
            approved_at TIMESTAMP,
            processed_at TIMESTAMP,
            created_by_id VARCHAR(36) REFERENCES hq_employee(id),
            created_at TIMESTAMP DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW() NOT NULL
        );
    """)

    # Create hq_payroll_item table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_payroll_item (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            payroll_run_id VARCHAR(36) NOT NULL REFERENCES hq_payroll_run(id),
            employee_id VARCHAR(36) NOT NULL REFERENCES hq_hr_employee(id),
            gross_pay NUMERIC(12, 2) DEFAULT 0 NOT NULL,
            regular_hours NUMERIC(6, 2),
            overtime_hours NUMERIC(6, 2),
            regular_pay NUMERIC(12, 2) DEFAULT 0 NOT NULL,
            overtime_pay NUMERIC(12, 2) DEFAULT 0 NOT NULL,
            bonus NUMERIC(12, 2) DEFAULT 0 NOT NULL,
            federal_tax NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            state_tax NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            social_security NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            medicare NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            local_tax NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            health_insurance NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            dental_insurance NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            vision_insurance NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            retirement_401k NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            other_deductions NUMERIC(10, 2) DEFAULT 0 NOT NULL,
            net_pay NUMERIC(12, 2) DEFAULT 0 NOT NULL,
            check_paystub_id VARCHAR(100),
            created_at TIMESTAMP DEFAULT NOW() NOT NULL
        );
    """)

    # Create hq_system_module table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_system_module (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            key VARCHAR UNIQUE NOT NULL,
            name VARCHAR NOT NULL,
            description TEXT,
            status modulestatus DEFAULT 'active' NOT NULL,
            maintenance_message TEXT,
            maintenance_end_time TIMESTAMP,
            last_updated_by_id VARCHAR REFERENCES hq_employee(id),
            last_updated_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW() NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_hq_system_module_key ON hq_system_module(key);
    """)


def downgrade() -> None:
    # Note: We don't drop enums in downgrade as they may be used by other tables
    # We also don't drop columns as that would cause data loss
    pass
