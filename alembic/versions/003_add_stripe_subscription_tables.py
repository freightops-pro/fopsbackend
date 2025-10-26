"""Add Stripe subscription tables

Revision ID: 003_add_stripe_subscription_tables
Revises: 002_add_hq_admin
Create Date: 2024-01-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_add_stripe_subscription_tables'
down_revision = '002_add_hq_admin'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create subscription_plans table
    op.create_table('subscription_plans',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('stripe_price_id', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_monthly', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('interval', sa.String(), nullable=False),
        sa.Column('features', sa.Text(), nullable=True),
        sa.Column('max_users', sa.Integer(), nullable=True),
        sa.Column('max_vehicles', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_popular', sa.Boolean(), nullable=True, default=False),
        sa.Column('sort_order', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_plans_id'), 'subscription_plans', ['id'], unique=False)
    op.create_index(op.f('ix_subscription_plans_stripe_price_id'), 'subscription_plans', ['stripe_price_id'], unique=True)

    # Create stripe_customers table
    op.create_table('stripe_customers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('stripe_customer_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address_line1', sa.String(), nullable=True),
        sa.Column('address_line2', sa.String(), nullable=True),
        sa.Column('city', sa.String(), nullable=True),
        sa.Column('state', sa.String(), nullable=True),
        sa.Column('postal_code', sa.String(), nullable=True),
        sa.Column('country', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stripe_customers_id'), 'stripe_customers', ['id'], unique=False)
    op.create_index(op.f('ix_stripe_customers_company_id'), 'stripe_customers', ['company_id'], unique=True)
    op.create_index(op.f('ix_stripe_customers_stripe_customer_id'), 'stripe_customers', ['stripe_customer_id'], unique=True)

    # Create company_subscriptions table
    op.create_table('company_subscriptions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('stripe_customer_id', sa.String(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(), nullable=False),
        sa.Column('plan_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=True, default=False),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(), nullable=False, default='usd'),
        sa.Column('interval', sa.String(), nullable=False),
        sa.Column('trial_start', sa.DateTime(), nullable=True),
        sa.Column('trial_end', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['plan_id'], ['subscription_plans.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_company_subscriptions_id'), 'company_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_company_subscriptions_company_id'), 'company_subscriptions', ['company_id'], unique=True)
    op.create_index(op.f('ix_company_subscriptions_stripe_subscription_id'), 'company_subscriptions', ['stripe_subscription_id'], unique=True)
    op.create_index(op.f('ix_company_subscriptions_stripe_customer_id'), 'company_subscriptions', ['stripe_customer_id'], unique=False)

    # Create payment_methods table
    op.create_table('payment_methods',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('stripe_payment_method_id', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True, default=False),
        sa.Column('card_brand', sa.String(), nullable=True),
        sa.Column('card_last4', sa.String(), nullable=True),
        sa.Column('card_exp_month', sa.Integer(), nullable=True),
        sa.Column('card_exp_year', sa.Integer(), nullable=True),
        sa.Column('bank_name', sa.String(), nullable=True),
        sa.Column('bank_account_last4', sa.String(), nullable=True),
        sa.Column('bank_account_type', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payment_methods_id'), 'payment_methods', ['id'], unique=False)
    op.create_index(op.f('ix_payment_methods_stripe_payment_method_id'), 'payment_methods', ['stripe_payment_method_id'], unique=True)

    # Create stripe_invoices table
    op.create_table('stripe_invoices',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('stripe_invoice_id', sa.String(), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(), nullable=True),
        sa.Column('amount_due', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('amount_remaining', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('currency', sa.String(), nullable=False, default='usd'),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('paid', sa.Boolean(), nullable=True, default=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('invoice_pdf', sa.String(), nullable=True),
        sa.Column('hosted_invoice_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stripe_invoices_id'), 'stripe_invoices', ['id'], unique=False)
    op.create_index(op.f('ix_stripe_invoices_stripe_invoice_id'), 'stripe_invoices', ['stripe_invoice_id'], unique=True)
    op.create_index(op.f('ix_stripe_invoices_stripe_subscription_id'), 'stripe_invoices', ['stripe_subscription_id'], unique=False)

    # Create stripe_webhook_events table
    op.create_table('stripe_webhook_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('stripe_event_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=True, default=False),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('event_data', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stripe_webhook_events_id'), 'stripe_webhook_events', ['id'], unique=False)
    op.create_index(op.f('ix_stripe_webhook_events_stripe_event_id'), 'stripe_webhook_events', ['stripe_event_id'], unique=True)
    op.create_index(op.f('ix_stripe_webhook_events_event_type'), 'stripe_webhook_events', ['event_type'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_stripe_webhook_events_event_type'), table_name='stripe_webhook_events')
    op.drop_index(op.f('ix_stripe_webhook_events_stripe_event_id'), table_name='stripe_webhook_events')
    op.drop_index(op.f('ix_stripe_webhook_events_id'), table_name='stripe_webhook_events')
    op.drop_index(op.f('ix_invoices_stripe_subscription_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_stripe_invoice_id'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_id'), table_name='invoices')
    op.drop_index(op.f('ix_payment_methods_stripe_payment_method_id'), table_name='payment_methods')
    op.drop_index(op.f('ix_payment_methods_id'), table_name='payment_methods')
    op.drop_index(op.f('ix_company_subscriptions_stripe_customer_id'), table_name='company_subscriptions')
    op.drop_index(op.f('ix_company_subscriptions_stripe_subscription_id'), table_name='company_subscriptions')
    op.drop_index(op.f('ix_company_subscriptions_company_id'), table_name='company_subscriptions')
    op.drop_index(op.f('ix_company_subscriptions_id'), table_name='company_subscriptions')
    op.drop_index(op.f('ix_stripe_customers_stripe_customer_id'), table_name='stripe_customers')
    op.drop_index(op.f('ix_stripe_customers_company_id'), table_name='stripe_customers')
    op.drop_index(op.f('ix_stripe_customers_id'), table_name='stripe_customers')
    op.drop_index(op.f('ix_subscription_plans_stripe_price_id'), table_name='subscription_plans')
    op.drop_index(op.f('ix_subscription_plans_id'), table_name='subscription_plans')
    
    # Drop tables
    op.drop_table('stripe_webhook_events')
    op.drop_table('stripe_invoices')
    op.drop_table('payment_methods')
    op.drop_table('company_subscriptions')
    op.drop_table('stripe_customers')
    op.drop_table('subscription_plans')
