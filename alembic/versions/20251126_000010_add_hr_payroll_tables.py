"""Add HR and Payroll tables.

Revision ID: 20251126_000010
Revises: 20251122_000009
Create Date: 2025-11-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251126_000010'
down_revision = '20251122_000009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create worker table
    op.create_table(
        'worker',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('type', sa.Enum('employee', 'contractor', name='workertype'), nullable=False),
        sa.Column('role', sa.Enum('driver', 'office', 'mechanic', 'dispatcher', 'other', name='workerrole'), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('tax_id', sa.Text(), nullable=True),
        sa.Column('tax_form_status', sa.JSON(), nullable=True),
        sa.Column('pay_default', sa.JSON(), nullable=True),
        sa.Column('bank_info', sa.JSON(), nullable=True),
        sa.Column('gusto_id', sa.String(), nullable=True),
        sa.Column('gusto_employee_id', sa.String(), nullable=True),
        sa.Column('gusto_contractor_id', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'terminated', name='workerstatus'), nullable=False),
        sa.Column('hire_date', sa.Date(), nullable=True),
        sa.Column('termination_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_company_id'), 'worker', ['company_id'], unique=False)
    op.create_index(op.f('ix_worker_gusto_id'), 'worker', ['gusto_id'], unique=True)

    # Create worker_document table
    op.create_table(
        'worker_document',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=False),
        sa.Column('doc_type', sa.Enum('W4', 'W9', 'I9', 'CDL', 'MEDCARD', 'SSN', 'LICENSE', 'OTHER', name='documenttype'), nullable=False),
        sa.Column('file_url', sa.String(), nullable=False),
        sa.Column('expires_at', sa.Date(), nullable=True),
        sa.Column('uploaded_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['worker_id'], ['worker.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_document_worker_id'), 'worker_document', ['worker_id'], unique=False)

    # Create pay_rule table
    op.create_table(
        'pay_rule',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=True),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('rule_type', sa.Enum('hourly', 'salary', 'mileage', 'percentage', 'piece', name='payruletype'), nullable=False),
        sa.Column('rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('additional', sa.JSON(), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['worker_id'], ['worker.id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pay_rule_worker_id'), 'pay_rule', ['worker_id'], unique=False)
    op.create_index(op.f('ix_pay_rule_company_id'), 'pay_rule', ['company_id'], unique=False)

    # Create deduction table
    op.create_table(
        'deduction',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=False),
        sa.Column('type', sa.Enum('tax', 'benefit', 'escrow', 'fuel_card', 'lease', 'garnishment', 'advance', name='deductiontype'), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('percentage', sa.Numeric(5, 4), nullable=True),
        sa.Column('frequency', sa.Enum('per_payroll', 'weekly', 'monthly', 'one_time', name='deductionfrequency'), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['worker_id'], ['worker.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_deduction_worker_id'), 'deduction', ['worker_id'], unique=False)

    # Create payroll_run table
    op.create_table(
        'payroll_run',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('pay_period_start', sa.Date(), nullable=False),
        sa.Column('pay_period_end', sa.Date(), nullable=False),
        sa.Column('run_by', sa.String(), nullable=True),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'preview', 'approved', 'submitted', 'completed', 'failed', name='payrollrunstatus'), nullable=False),
        sa.Column('totals', sa.JSON(), nullable=True),
        sa.Column('gusto_payroll_id', sa.String(), nullable=True),
        sa.Column('gusto_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.ForeignKeyConstraint(['run_by'], ['user.id'], ),
        sa.ForeignKeyConstraint(['approved_by'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payroll_run_company_id'), 'payroll_run', ['company_id'], unique=False)

    # Create pay_item table
    op.create_table(
        'pay_item',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('payroll_run_id', sa.String(), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=False),
        sa.Column('type', sa.Enum('miles', 'hours', 'bonus', 'accessorial', 'reimbursement', 'deduction', 'percentage', name='payitemtype'), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['payroll_run_id'], ['payroll_run.id'], ),
        sa.ForeignKeyConstraint(['worker_id'], ['worker.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pay_item_payroll_run_id'), 'pay_item', ['payroll_run_id'], unique=False)
    op.create_index(op.f('ix_pay_item_worker_id'), 'pay_item', ['worker_id'], unique=False)

    # Create settlement table
    op.create_table(
        'settlement',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('payroll_run_id', sa.String(), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=False),
        sa.Column('gross', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_deductions', sa.Numeric(10, 2), nullable=False),
        sa.Column('net', sa.Numeric(10, 2), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('gusto_payment_id', sa.String(), nullable=True),
        sa.Column('gusto_status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['payroll_run_id'], ['payroll_run.id'], ),
        sa.ForeignKeyConstraint(['worker_id'], ['worker.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlement_payroll_run_id'), 'settlement', ['payroll_run_id'], unique=False)
    op.create_index(op.f('ix_settlement_worker_id'), 'settlement', ['worker_id'], unique=False)

    # Create gusto_sync table
    op.create_table(
        'gusto_sync',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('entity_id', sa.String(), nullable=True),
        sa.Column('request_payload', sa.JSON(), nullable=True),
        sa.Column('response_payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('run_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gusto_sync_company_id'), 'gusto_sync', ['company_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_gusto_sync_company_id'), table_name='gusto_sync')
    op.drop_table('gusto_sync')

    op.drop_index(op.f('ix_settlement_worker_id'), table_name='settlement')
    op.drop_index(op.f('ix_settlement_payroll_run_id'), table_name='settlement')
    op.drop_table('settlement')

    op.drop_index(op.f('ix_pay_item_worker_id'), table_name='pay_item')
    op.drop_index(op.f('ix_pay_item_payroll_run_id'), table_name='pay_item')
    op.drop_table('pay_item')

    op.drop_index(op.f('ix_payroll_run_company_id'), table_name='payroll_run')
    op.drop_table('payroll_run')

    op.drop_index(op.f('ix_deduction_worker_id'), table_name='deduction')
    op.drop_table('deduction')

    op.drop_index(op.f('ix_pay_rule_company_id'), table_name='pay_rule')
    op.drop_index(op.f('ix_pay_rule_worker_id'), table_name='pay_rule')
    op.drop_table('pay_rule')

    op.drop_index(op.f('ix_worker_document_worker_id'), table_name='worker_document')
    op.drop_table('worker_document')

    op.drop_index(op.f('ix_worker_gusto_id'), table_name='worker')
    op.drop_index(op.f('ix_worker_company_id'), table_name='worker')
    op.drop_table('worker')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS payrollrunstatus')
    op.execute('DROP TYPE IF EXISTS deductionfrequency')
    op.execute('DROP TYPE IF EXISTS deductiontype')
    op.execute('DROP TYPE IF EXISTS payitemtype')
    op.execute('DROP TYPE IF EXISTS payruletype')
    op.execute('DROP TYPE IF EXISTS documenttype')
    op.execute('DROP TYPE IF EXISTS workerstatus')
    op.execute('DROP TYPE IF EXISTS workerrole')
    op.execute('DROP TYPE IF EXISTS workertype')
