"""Add Plaid integration for external bank accounts.

Revision ID: 20251215_add_plaid_banking
Revises: previous_migration_id
Create Date: 2025-12-15
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers
revision = '20251215_add_plaid_banking'
down_revision = '20251215_000001'  # Revises approval and maintenance tables
branch_labels = None
depends_on = None


def upgrade():
    # Plaid Item (represents a bank connection)
    op.create_table(
        'plaid_item',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id'), nullable=False, index=True),

        # Plaid identifiers
        sa.Column('item_id', sa.String(), nullable=False, unique=True, index=True),
        sa.Column('access_token', sa.Text(), nullable=False),  # Encrypted in production
        sa.Column('institution_id', sa.String(), nullable=True),
        sa.Column('institution_name', sa.String(), nullable=True),

        # Status
        sa.Column('status', sa.String(), nullable=False, default='active'),  # active, error, requires_reauth
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Sync tracking
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('sync_cursor', sa.String(), nullable=True),  # For incremental updates

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),

        sa.Index('idx_plaid_item_company', 'company_id'),
        sa.Index('idx_plaid_item_status', 'status'),
    )

    # Plaid Account (bank account within a Plaid Item)
    op.create_table(
        'plaid_account',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id'), nullable=False, index=True),
        sa.Column('item_id', sa.String(), sa.ForeignKey('plaid_item.id'), nullable=False, index=True),

        # Plaid identifiers
        sa.Column('account_id', sa.String(), nullable=False, unique=True, index=True),  # Plaid's account_id

        # Account details
        sa.Column('name', sa.String(), nullable=False),  # e.g., "Business Checking"
        sa.Column('official_name', sa.String(), nullable=True),
        sa.Column('account_type', sa.String(), nullable=False),  # depository, credit, loan, investment
        sa.Column('account_subtype', sa.String(), nullable=True),  # checking, savings, credit card, etc.

        # Account numbers (masked)
        sa.Column('mask', sa.String(), nullable=True),  # Last 4 digits

        # Balances
        sa.Column('current_balance', sa.Numeric(14, 2), nullable=True),
        sa.Column('available_balance', sa.Numeric(14, 2), nullable=True),
        sa.Column('balance_limit', sa.Numeric(14, 2), nullable=True),
        sa.Column('currency_code', sa.String(), nullable=False, default='USD'),

        # Link to Chart of Accounts (for reconciliation)
        sa.Column('ledger_account_code', sa.String(), nullable=True),  # e.g., "1000" for Cash - Operating

        # Status
        sa.Column('enabled_for_sync', sa.Boolean(), nullable=False, default=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),

        sa.Index('idx_plaid_account_company', 'company_id'),
        sa.Index('idx_plaid_account_item', 'item_id'),
    )

    # Plaid Transaction (transactions from external banks)
    op.create_table(
        'plaid_transaction',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id'), nullable=False, index=True),
        sa.Column('account_id', sa.String(), sa.ForeignKey('plaid_account.id'), nullable=False, index=True),

        # Plaid identifiers
        sa.Column('transaction_id', sa.String(), nullable=False, unique=True, index=True),  # Plaid's transaction_id

        # Transaction details
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency_code', sa.String(), nullable=False, default='USD'),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('merchant_name', sa.String(), nullable=True),

        # Categorization
        sa.Column('category_primary', sa.String(), nullable=True),  # e.g., "Travel", "Food and Drink"
        sa.Column('category_detailed', sa.String(), nullable=True),
        sa.Column('category_id', sa.String(), nullable=True),

        # Dates
        sa.Column('date', sa.Date(), nullable=False, index=True),  # Transaction date
        sa.Column('authorized_date', sa.Date(), nullable=True),
        sa.Column('posted_date', sa.Date(), nullable=True),

        # Status
        sa.Column('pending', sa.Boolean(), nullable=False, default=False),
        sa.Column('transaction_type', sa.String(), nullable=True),  # special, place, digital, etc.

        # Payment details
        sa.Column('payment_channel', sa.String(), nullable=True),  # online, in store, other
        sa.Column('payment_method', sa.String(), nullable=True),

        # Location
        sa.Column('location_address', sa.String(), nullable=True),
        sa.Column('location_city', sa.String(), nullable=True),
        sa.Column('location_state', sa.String(), nullable=True),
        sa.Column('location_zip', sa.String(), nullable=True),

        # Reconciliation tracking (foreign key will be added when ledger_entry table exists)
        sa.Column('matched_ledger_entry_id', sa.String(), nullable=True, index=True),
        sa.Column('reconciled', sa.Boolean(), nullable=False, default=False),
        sa.Column('reconciled_at', sa.DateTime(), nullable=True),
        sa.Column('reconciled_by', sa.String(), nullable=True),

        # Auto-categorization (from allocation rules)
        sa.Column('suggested_account_code', sa.String(), nullable=True),
        sa.Column('suggested_category', sa.String(), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),

        sa.Index('idx_plaid_transaction_company', 'company_id'),
        sa.Index('idx_plaid_transaction_account', 'account_id'),
        sa.Index('idx_plaid_transaction_date', 'date'),
        sa.Index('idx_plaid_transaction_reconciled', 'reconciled'),
    )

    # Add reconciliation support to existing BankingTransaction (for Synctera accounts)
    # Foreign key to ledger_entry will be added when that table is created
    op.add_column('banking_transaction', sa.Column('matched_ledger_entry_id', sa.String(), nullable=True))
    op.add_column('banking_transaction', sa.Column('reconciled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('banking_transaction', sa.Column('reconciled_at', sa.DateTime(), nullable=True))

    op.create_index('idx_banking_transaction_reconciled', 'banking_transaction', ['reconciled'])


def downgrade():
    op.drop_index('idx_banking_transaction_reconciled', 'banking_transaction')
    op.drop_column('banking_transaction', 'reconciled_at')
    op.drop_column('banking_transaction', 'reconciled')
    op.drop_column('banking_transaction', 'matched_ledger_entry_id')

    op.drop_table('plaid_transaction')
    op.drop_table('plaid_account')
    op.drop_table('plaid_item')
