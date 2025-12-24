"""add_hq_banking_tables

Revision ID: 9ba652cbfdda
Revises: 20251223_000001
Create Date: 2025-12-23 19:51:43.491732

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9ba652cbfdda'
down_revision = '20251223_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create HQ Banking Audit Log table
    op.create_table('hq_banking_audit_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('performed_by', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.String(), nullable=True),
        sa.Column('action_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.ForeignKeyConstraint(['performed_by'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_banking_audit_log_company_id'), 'hq_banking_audit_log', ['company_id'], unique=False)
    op.create_index(op.f('ix_hq_banking_audit_log_performed_by'), 'hq_banking_audit_log', ['performed_by'], unique=False)

    # Create HQ Fraud Alert table
    op.create_table('hq_fraud_alert',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('synctera_alert_id', sa.String(), nullable=True),
        sa.Column('transaction_id', sa.String(), nullable=True),
        sa.Column('card_id', sa.String(), nullable=True),
        sa.Column('account_id', sa.String(), nullable=True),
        sa.Column('alert_type', sa.String(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('resolved_by', sa.String(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['hq_employee.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_fraud_alert_account_id'), 'hq_fraud_alert', ['account_id'], unique=False)
    op.create_index(op.f('ix_hq_fraud_alert_card_id'), 'hq_fraud_alert', ['card_id'], unique=False)
    op.create_index(op.f('ix_hq_fraud_alert_company_id'), 'hq_fraud_alert', ['company_id'], unique=False)
    op.create_index(op.f('ix_hq_fraud_alert_synctera_alert_id'), 'hq_fraud_alert', ['synctera_alert_id'], unique=True)
    op.create_index(op.f('ix_hq_fraud_alert_transaction_id'), 'hq_fraud_alert', ['transaction_id'], unique=False)


def downgrade() -> None:
    # Drop HQ Fraud Alert table
    op.drop_index(op.f('ix_hq_fraud_alert_transaction_id'), table_name='hq_fraud_alert')
    op.drop_index(op.f('ix_hq_fraud_alert_synctera_alert_id'), table_name='hq_fraud_alert')
    op.drop_index(op.f('ix_hq_fraud_alert_company_id'), table_name='hq_fraud_alert')
    op.drop_index(op.f('ix_hq_fraud_alert_card_id'), table_name='hq_fraud_alert')
    op.drop_index(op.f('ix_hq_fraud_alert_account_id'), table_name='hq_fraud_alert')
    op.drop_table('hq_fraud_alert')

    # Drop HQ Banking Audit Log table
    op.drop_index(op.f('ix_hq_banking_audit_log_performed_by'), table_name='hq_banking_audit_log')
    op.drop_index(op.f('ix_hq_banking_audit_log_company_id'), table_name='hq_banking_audit_log')
    op.drop_table('hq_banking_audit_log')
