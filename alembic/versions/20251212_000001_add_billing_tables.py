"""add_billing_tables

Revision ID: 20251212_000001
Revises: e9f31e598fb6
Create Date: 2025-12-12 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251212_000001'
down_revision = 'e9f31e598fb6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create billing_subscription table
    op.create_table(
        'billing_subscription',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='trialing'),
        sa.Column('subscription_type', sa.String(), nullable=False, server_default='self_serve'),
        sa.Column('billing_cycle', sa.String(), nullable=False, server_default='monthly'),
        sa.Column('truck_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('base_price_per_truck', sa.Numeric(10, 2), nullable=False, server_default='49.00'),
        sa.Column('total_monthly_cost', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('trial_days_remaining', sa.Integer(), nullable=True),
        sa.Column('current_period_start', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('current_period_end', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('stripe_customer_id', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_subscription_company_id'), 'billing_subscription', ['company_id'], unique=True)
    op.create_index(op.f('ix_billing_subscription_stripe_subscription_id'), 'billing_subscription', ['stripe_subscription_id'], unique=True)
    op.create_index(op.f('ix_billing_subscription_stripe_customer_id'), 'billing_subscription', ['stripe_customer_id'], unique=False)
    op.create_foreign_key('fk_billing_subscription_company_id', 'billing_subscription', 'company', ['company_id'], ['id'])

    # Create billing_subscription_addon table
    op.create_table(
        'billing_subscription_addon',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('subscription_id', sa.String(), nullable=False),
        sa.Column('service', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('monthly_cost', sa.Numeric(10, 2), nullable=False),
        sa.Column('employee_count', sa.Integer(), nullable=True),
        sa.Column('per_employee_cost', sa.Numeric(10, 2), nullable=True),
        sa.Column('has_trial', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_subscription_addon_subscription_id'), 'billing_subscription_addon', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_billing_subscription_addon_stripe_subscription_id'), 'billing_subscription_addon', ['stripe_subscription_id'], unique=False)
    op.create_foreign_key('fk_billing_subscription_addon_subscription_id', 'billing_subscription_addon', 'billing_subscription', ['subscription_id'], ['id'])

    # Create billing_payment_method table
    op.create_table(
        'billing_payment_method',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('payment_type', sa.String(), nullable=False, server_default='card'),
        sa.Column('card_details', sa.JSON(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('stripe_payment_method_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_payment_method_company_id'), 'billing_payment_method', ['company_id'], unique=False)
    op.create_index(op.f('ix_billing_payment_method_stripe_payment_method_id'), 'billing_payment_method', ['stripe_payment_method_id'], unique=True)
    op.create_foreign_key('fk_billing_payment_method_company_id', 'billing_payment_method', 'company', ['company_id'], ['id'])

    # Create billing_stripe_invoice table
    op.create_table(
        'billing_stripe_invoice',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('invoice_number', sa.String(), nullable=True),
        sa.Column('amount_due', sa.Numeric(10, 2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('invoice_created_at', sa.DateTime(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('invoice_pdf', sa.String(), nullable=True),
        sa.Column('stripe_invoice_id', sa.String(), nullable=False),
        sa.Column('line_items', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_stripe_invoice_company_id'), 'billing_stripe_invoice', ['company_id'], unique=False)
    op.create_index(op.f('ix_billing_stripe_invoice_stripe_invoice_id'), 'billing_stripe_invoice', ['stripe_invoice_id'], unique=True)
    op.create_foreign_key('fk_billing_stripe_invoice_company_id', 'billing_stripe_invoice', 'company', ['company_id'], ['id'])

    # Create billing_stripe_webhook_event table
    op.create_table(
        'billing_stripe_webhook_event',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('stripe_event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_stripe_webhook_event_stripe_event_id'), 'billing_stripe_webhook_event', ['stripe_event_id'], unique=True)
    op.create_index(op.f('ix_billing_stripe_webhook_event_event_type'), 'billing_stripe_webhook_event', ['event_type'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_billing_stripe_webhook_event_event_type'), table_name='billing_stripe_webhook_event')
    op.drop_index(op.f('ix_billing_stripe_webhook_event_stripe_event_id'), table_name='billing_stripe_webhook_event')
    op.drop_table('billing_stripe_webhook_event')

    op.drop_constraint('fk_billing_stripe_invoice_company_id', 'billing_stripe_invoice', type_='foreignkey')
    op.drop_index(op.f('ix_billing_stripe_invoice_stripe_invoice_id'), table_name='billing_stripe_invoice')
    op.drop_index(op.f('ix_billing_stripe_invoice_company_id'), table_name='billing_stripe_invoice')
    op.drop_table('billing_stripe_invoice')

    op.drop_constraint('fk_billing_payment_method_company_id', 'billing_payment_method', type_='foreignkey')
    op.drop_index(op.f('ix_billing_payment_method_stripe_payment_method_id'), table_name='billing_payment_method')
    op.drop_index(op.f('ix_billing_payment_method_company_id'), table_name='billing_payment_method')
    op.drop_table('billing_payment_method')

    op.drop_constraint('fk_billing_subscription_addon_subscription_id', 'billing_subscription_addon', type_='foreignkey')
    op.drop_index(op.f('ix_billing_subscription_addon_stripe_subscription_id'), table_name='billing_subscription_addon')
    op.drop_index(op.f('ix_billing_subscription_addon_subscription_id'), table_name='billing_subscription_addon')
    op.drop_table('billing_subscription_addon')

    op.drop_constraint('fk_billing_subscription_company_id', 'billing_subscription', type_='foreignkey')
    op.drop_index(op.f('ix_billing_subscription_stripe_customer_id'), table_name='billing_subscription')
    op.drop_index(op.f('ix_billing_subscription_stripe_subscription_id'), table_name='billing_subscription')
    op.drop_index(op.f('ix_billing_subscription_company_id'), table_name='billing_subscription')
    op.drop_table('billing_subscription')
