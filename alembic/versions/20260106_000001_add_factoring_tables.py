"""add factoring tables

Revision ID: 20260106_000001
Revises: 20260101_000001
Create Date: 2026-01-06 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20260106_000001'
down_revision: Union[str, None] = '20260101_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create factoring_providers table
    op.create_table(
        'factoring_providers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('api_endpoint', sa.String(), nullable=True),
        sa.Column('webhook_secret', sa.String(), nullable=True),
        sa.Column('factoring_rate', sa.Float(), nullable=False),
        sa.Column('advance_rate', sa.Float(), nullable=False, server_default='95.0'),
        sa.Column('payment_terms_days', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_configured', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_factoring_providers_company_id'), 'factoring_providers', ['company_id'], unique=False)
    op.create_index(op.f('ix_factoring_providers_id'), 'factoring_providers', ['id'], unique=False)

    # Create factoring_transactions table
    op.create_table(
        'factoring_transactions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('provider_id', sa.String(), nullable=False),
        sa.Column('load_id', sa.String(), nullable=False),
        sa.Column('invoice_id', sa.String(), nullable=True),
        sa.Column('invoice_amount', sa.Float(), nullable=False),
        sa.Column('factoring_fee', sa.Float(), nullable=False),
        sa.Column('advance_amount', sa.Float(), nullable=False),
        sa.Column('reserve_amount', sa.Float(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('external_reference_id', sa.String(), nullable=True),
        sa.Column('batch_id', sa.String(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('funded_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.Column('payment_method', sa.String(), nullable=True),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('documents_submitted', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('rejection_reason', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['provider_id'], ['factoring_providers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['load_id'], ['freight_load.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('ix_factoring_transactions_company_id'), 'factoring_transactions', ['company_id'], unique=False)
    op.create_index(op.f('ix_factoring_transactions_id'), 'factoring_transactions', ['id'], unique=False)
    op.create_index(op.f('ix_factoring_transactions_provider_id'), 'factoring_transactions', ['provider_id'], unique=False)
    op.create_index(op.f('ix_factoring_transactions_load_id'), 'factoring_transactions', ['load_id'], unique=False)
    op.create_index(op.f('ix_factoring_transactions_batch_id'), 'factoring_transactions', ['batch_id'], unique=False)
    op.create_index(op.f('ix_factoring_transactions_status'), 'factoring_transactions', ['status'], unique=False)

    # Add factoring columns to freight_load table
    op.add_column('freight_load', sa.Column('factoring_enabled', sa.String(), nullable=True))
    op.add_column('freight_load', sa.Column('factoring_status', sa.String(), nullable=True))
    op.add_column('freight_load', sa.Column('factoring_rate_override', sa.Float(), nullable=True))
    op.add_column('freight_load', sa.Column('factored_amount', sa.Numeric(12, 2), nullable=True))
    op.add_column('freight_load', sa.Column('factoring_fee_amount', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    # Remove factoring columns from freight_load table
    op.drop_column('freight_load', 'factoring_fee_amount')
    op.drop_column('freight_load', 'factored_amount')
    op.drop_column('freight_load', 'factoring_rate_override')
    op.drop_column('freight_load', 'factoring_status')
    op.drop_column('freight_load', 'factoring_enabled')

    # Drop factoring_transactions table
    op.drop_index(op.f('ix_factoring_transactions_status'), table_name='factoring_transactions')
    op.drop_index(op.f('ix_factoring_transactions_batch_id'), table_name='factoring_transactions')
    op.drop_index(op.f('ix_factoring_transactions_load_id'), table_name='factoring_transactions')
    op.drop_index(op.f('ix_factoring_transactions_provider_id'), table_name='factoring_transactions')
    op.drop_index(op.f('ix_factoring_transactions_id'), table_name='factoring_transactions')
    op.drop_index(op.f('ix_factoring_transactions_company_id'), table_name='factoring_transactions')
    op.drop_table('factoring_transactions')

    # Drop factoring_providers table
    op.drop_index(op.f('ix_factoring_providers_id'), table_name='factoring_providers')
    op.drop_index(op.f('ix_factoring_providers_company_id'), table_name='factoring_providers')
    op.drop_table('factoring_providers')
