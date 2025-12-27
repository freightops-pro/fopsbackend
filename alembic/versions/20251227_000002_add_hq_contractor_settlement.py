"""Add HQ contractor settlement table for 1099 payments.

Revision ID: 20251227_000002
Revises: 20251227_000001
Create Date: 2025-12-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251227_000002'
down_revision = '20251227_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create settlement status enum
    settlement_status_enum = postgresql.ENUM(
        'draft', 'pending_approval', 'approved', 'processing', 'paid', 'failed', 'cancelled',
        name='settlementstatus',
        create_type=False
    )

    # Create enum type if not exists
    op.execute("DO $$ BEGIN CREATE TYPE settlementstatus AS ENUM ('draft', 'pending_approval', 'approved', 'processing', 'paid', 'failed', 'cancelled'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    # Create contractor settlement table
    op.create_table(
        'hq_contractor_settlement',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('contractor_id', sa.String(), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('payment_date', sa.DateTime(), nullable=False),
        sa.Column('settlement_number', sa.String(), nullable=False),
        sa.Column('status', settlement_status_enum, nullable=False, server_default='draft'),
        sa.Column('items', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('commission_payment_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('total_commission', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total_bonus', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total_reimbursements', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total_deductions', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('net_payment', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('approved_by_id', sa.String(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('payment_method', sa.String(), nullable=True),
        sa.Column('created_by_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['contractor_id'], ['hq_employee.id'], ),
        sa.ForeignKeyConstraint(['approved_by_id'], ['hq_employee.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('settlement_number')
    )

    # Create indexes
    op.create_index('ix_hq_contractor_settlement_contractor_id', 'hq_contractor_settlement', ['contractor_id'])
    op.create_index('ix_hq_contractor_settlement_status', 'hq_contractor_settlement', ['status'])
    op.create_index('ix_hq_contractor_settlement_created_at', 'hq_contractor_settlement', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_hq_contractor_settlement_created_at', table_name='hq_contractor_settlement')
    op.drop_index('ix_hq_contractor_settlement_status', table_name='hq_contractor_settlement')
    op.drop_index('ix_hq_contractor_settlement_contractor_id', table_name='hq_contractor_settlement')
    op.drop_table('hq_contractor_settlement')
    op.execute("DROP TYPE IF EXISTS settlementstatus;")
