"""Add HQ HR and Payroll tables

Revision ID: 20251224_000003
Revises: 20251224_000002
Create Date: 2024-12-24 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251224_000003'
down_revision: Union[str, None] = '20251224_000002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create employment_type enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'employmenttype') THEN
                CREATE TYPE employmenttype AS ENUM ('full_time', 'part_time', 'contractor', 'intern');
            END IF;
        END $$;
    """)

    # Create hr_employee_status enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'hremployeestatus') THEN
                CREATE TYPE hremployeestatus AS ENUM ('active', 'terminated', 'on_leave', 'onboarding');
            END IF;
        END $$;
    """)

    # Create pay_frequency enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payfrequency') THEN
                CREATE TYPE payfrequency AS ENUM ('weekly', 'biweekly', 'semimonthly', 'monthly');
            END IF;
        END $$;
    """)

    # Create payroll_status enum
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payrollstatus') THEN
                CREATE TYPE payrollstatus AS ENUM (
                    'draft', 'pending_approval', 'approved', 'processing', 'completed', 'failed', 'cancelled'
                );
            END IF;
        END $$;
    """)

    # Create hq_hr_employee table
    op.create_table(
        'hq_hr_employee',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('employee_number', sa.String(20), unique=True, nullable=False),
        # Personal info
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(50), nullable=True),
        # Employment details
        sa.Column('employment_type', sa.Enum('full_time', 'part_time', 'contractor', 'intern', name='employmenttype', create_type=False), default='full_time', nullable=False),
        sa.Column('status', sa.Enum('active', 'terminated', 'on_leave', 'onboarding', name='hremployeestatus', create_type=False), default='onboarding', nullable=False),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(100), nullable=True),
        sa.Column('manager_id', sa.String(36), sa.ForeignKey('hq_hr_employee.id'), nullable=True),
        sa.Column('hire_date', sa.DateTime, nullable=True),
        sa.Column('termination_date', sa.DateTime, nullable=True),
        # Compensation
        sa.Column('pay_frequency', sa.Enum('weekly', 'biweekly', 'semimonthly', 'monthly', name='payfrequency', create_type=False), default='biweekly', nullable=False),
        sa.Column('annual_salary', sa.Numeric(12, 2), nullable=True),
        sa.Column('hourly_rate', sa.Numeric(8, 2), nullable=True),
        # Address
        sa.Column('address_line1', sa.String(255), nullable=True),
        sa.Column('address_line2', sa.String(255), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('state', sa.String(50), nullable=True),
        sa.Column('zip_code', sa.String(20), nullable=True),
        # Check integration
        sa.Column('check_employee_id', sa.String(100), nullable=True, unique=True),
        # Sensitive data
        sa.Column('ssn_last_four', sa.String(4), nullable=True),
        sa.Column('date_of_birth', sa.DateTime, nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hq_hr_employee_number', 'hq_hr_employee', ['employee_number'])
    op.create_index('ix_hq_hr_employee_email', 'hq_hr_employee', ['email'])
    op.create_index('ix_hq_hr_employee_status', 'hq_hr_employee', ['status'])
    op.create_index('ix_hq_hr_employee_department', 'hq_hr_employee', ['department'])

    # Create hq_payroll_run table
    op.create_table(
        'hq_payroll_run',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('payroll_number', sa.String(20), unique=True, nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending_approval', 'approved', 'processing', 'completed', 'failed', 'cancelled', name='payrollstatus', create_type=False), default='draft', nullable=False),
        sa.Column('pay_period_start', sa.DateTime, nullable=False),
        sa.Column('pay_period_end', sa.DateTime, nullable=False),
        sa.Column('pay_date', sa.DateTime, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        # Totals
        sa.Column('total_gross', sa.Numeric(14, 2), default=0, nullable=False),
        sa.Column('total_taxes', sa.Numeric(14, 2), default=0, nullable=False),
        sa.Column('total_deductions', sa.Numeric(14, 2), default=0, nullable=False),
        sa.Column('total_net', sa.Numeric(14, 2), default=0, nullable=False),
        sa.Column('employee_count', sa.Integer, default=0, nullable=False),
        # Check integration
        sa.Column('check_payroll_id', sa.String(100), nullable=True, unique=True),
        # Approval workflow
        sa.Column('approved_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime, nullable=True),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('created_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hq_payroll_run_number', 'hq_payroll_run', ['payroll_number'])
    op.create_index('ix_hq_payroll_run_status', 'hq_payroll_run', ['status'])
    op.create_index('ix_hq_payroll_run_pay_date', 'hq_payroll_run', ['pay_date'])

    # Create hq_payroll_item table
    op.create_table(
        'hq_payroll_item',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('payroll_run_id', sa.String(36), sa.ForeignKey('hq_payroll_run.id'), nullable=False),
        sa.Column('employee_id', sa.String(36), sa.ForeignKey('hq_hr_employee.id'), nullable=False),
        # Earnings
        sa.Column('gross_pay', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('regular_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('overtime_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('regular_pay', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('overtime_pay', sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column('bonus', sa.Numeric(12, 2), default=0, nullable=False),
        # Taxes
        sa.Column('federal_tax', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('state_tax', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('social_security', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('medicare', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('local_tax', sa.Numeric(10, 2), default=0, nullable=False),
        # Deductions (Benefits)
        sa.Column('health_insurance', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('dental_insurance', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('vision_insurance', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('retirement_401k', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('other_deductions', sa.Numeric(10, 2), default=0, nullable=False),
        # Net
        sa.Column('net_pay', sa.Numeric(12, 2), default=0, nullable=False),
        # Check integration
        sa.Column('check_paystub_id', sa.String(100), nullable=True),
        # Timestamp
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_hq_payroll_item_run', 'hq_payroll_item', ['payroll_run_id'])
    op.create_index('ix_hq_payroll_item_employee', 'hq_payroll_item', ['employee_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_hq_payroll_item_employee', 'hq_payroll_item')
    op.drop_index('ix_hq_payroll_item_run', 'hq_payroll_item')
    op.drop_table('hq_payroll_item')

    op.drop_index('ix_hq_payroll_run_pay_date', 'hq_payroll_run')
    op.drop_index('ix_hq_payroll_run_status', 'hq_payroll_run')
    op.drop_index('ix_hq_payroll_run_number', 'hq_payroll_run')
    op.drop_table('hq_payroll_run')

    op.drop_index('ix_hq_hr_employee_department', 'hq_hr_employee')
    op.drop_index('ix_hq_hr_employee_status', 'hq_hr_employee')
    op.drop_index('ix_hq_hr_employee_email', 'hq_hr_employee')
    op.drop_index('ix_hq_hr_employee_number', 'hq_hr_employee')
    op.drop_table('hq_hr_employee')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS payrollstatus")
    op.execute("DROP TYPE IF EXISTS payfrequency")
    op.execute("DROP TYPE IF EXISTS hremployeestatus")
    op.execute("DROP TYPE IF EXISTS employmenttype")
