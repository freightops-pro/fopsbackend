"""Add banking transfer and ACH recipient tables

Revision ID: 20251216_add_banking_transfers
Revises: 20251215_add_plaid_banking
Create Date: 2025-12-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '20251216_add_banking_transfers'
down_revision = '20251215_add_plaid_banking'
branch_labels = None
depends_on = None


def upgrade():
    # ACH Recipient table (create first since banking_transfer references it)
    op.create_table(
        'banking_ach_recipient',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id'), nullable=False, index=True),

        # Recipient details
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('routing_number', sa.String(9), nullable=False),
        sa.Column('account_number', sa.String(), nullable=False),  # Encrypted in production
        sa.Column('account_type', sa.String(), nullable=False),  # checking, savings

        # Optional metadata
        sa.Column('nickname', sa.String(), nullable=True),  # User-friendly name
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),  # Micro-deposit verification

        # Usage tracking
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('total_transfers', sa.Integer(), nullable=False, default=0),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),

        sa.Index('idx_ach_recipient_company', 'company_id', 'is_active'),
    )

    # Banking Transfer table (create after banking_ach_recipient)
    op.create_table(
        'banking_transfer',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id'), nullable=False, index=True),

        # Transfer type and status
        sa.Column('transfer_type', sa.String(), nullable=False, index=True),  # internal, ach, wire
        sa.Column('status', sa.String(), nullable=False, default='pending', index=True),  # pending, processing, completed, failed, cancelled

        # Account references
        sa.Column('from_account_id', sa.String(), nullable=True, index=True),  # Source account (Synctera or Plaid)
        sa.Column('to_account_id', sa.String(), nullable=True, index=True),    # Destination account (for internal transfers)

        # Amount and currency
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, default='USD'),
        sa.Column('fee_amount', sa.Numeric(8, 2), nullable=True, default=0.0),

        # Description and memo
        sa.Column('description', sa.String(255), nullable=True),

        # ACH recipient details (for ACH transfers)
        sa.Column('recipient_id', sa.String(), sa.ForeignKey('banking_ach_recipient.id'), nullable=True, index=True),
        sa.Column('recipient_name', sa.String(), nullable=True),
        sa.Column('recipient_routing_number', sa.String(9), nullable=True),
        sa.Column('recipient_account_number', sa.String(), nullable=True),
        sa.Column('recipient_account_type', sa.String(), nullable=True),  # checking, savings

        # Wire transfer details
        sa.Column('recipient_bank_name', sa.String(), nullable=True),
        sa.Column('wire_type', sa.String(), nullable=True),  # domestic, international
        sa.Column('recipient_swift_code', sa.String(), nullable=True),
        sa.Column('recipient_address', sa.JSON(), nullable=True),

        # Scheduling
        sa.Column('scheduled_date', sa.DateTime(), nullable=True, index=True),
        sa.Column('estimated_completion_date', sa.DateTime(), nullable=True),

        # Execution tracking
        sa.Column('initiated_by', sa.String(), sa.ForeignKey('user.id'), nullable=False, index=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),

        # External reference (Synctera/Plaid transaction ID)
        sa.Column('external_id', sa.String(), nullable=True, index=True),

        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow, index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),

        # Indexes
        sa.Index('idx_banking_transfer_company_created', 'company_id', 'created_at'),
        sa.Index('idx_banking_transfer_type_status', 'transfer_type', 'status'),
        sa.Index('idx_banking_transfer_from_account', 'from_account_id', 'created_at'),
    )

    # Add transfer tracking to existing banking_account table
    op.add_column('banking_account',
        sa.Column('total_transfers_sent', sa.Integer(), nullable=False, server_default='0',
        comment='Count of transfers sent from this account'))

    op.add_column('banking_account',
        sa.Column('total_transfers_received', sa.Integer(), nullable=False, server_default='0',
        comment='Count of transfers received to this account'))

    op.add_column('banking_account',
        sa.Column('daily_transfer_limit', sa.Numeric(12, 2), nullable=True,
        comment='Daily transfer limit (USD)'))

    op.add_column('banking_account',
        sa.Column('monthly_transfer_limit', sa.Numeric(12, 2), nullable=True,
        comment='Monthly transfer limit (USD)'))


def downgrade():
    # Remove columns from banking_account
    op.drop_column('banking_account', 'monthly_transfer_limit')
    op.drop_column('banking_account', 'daily_transfer_limit')
    op.drop_column('banking_account', 'total_transfers_received')
    op.drop_column('banking_account', 'total_transfers_sent')

    # Drop tables (reverse order - drop banking_transfer first since it references banking_ach_recipient)
    op.drop_table('banking_transfer')
    op.drop_table('banking_ach_recipient')
