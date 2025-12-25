"""Create HQ HR tables

Revision ID: 20251225_000003
Revises: 20251225_000002
Create Date: 2025-12-25 07:00:00.000000

Creates the HR/payroll tables:
- hq_hr_employee
- hq_payroll_run
- hq_payroll_item
- hq_system_module
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251225_000003"
down_revision: Union[str, None] = "20251225_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
    op.execute("DROP TABLE IF EXISTS hq_payroll_item CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_payroll_run CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_hr_employee CASCADE;")
    op.execute("DROP TABLE IF EXISTS hq_system_module CASCADE;")
