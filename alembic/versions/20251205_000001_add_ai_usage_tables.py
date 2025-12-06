"""add ai usage tables

Revision ID: 20251205_000001
Revises: 752eb60d0550
Create Date: 2025-12-05 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251205_000001'
down_revision = '752eb60d0550'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create AI Usage Log table
    op.create_table(
        'ai_usage_log',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('operation_type', sa.String(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('entity_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_usage_log_company_id'), 'ai_usage_log', ['company_id'], unique=False)
    op.create_index(op.f('ix_ai_usage_log_user_id'), 'ai_usage_log', ['user_id'], unique=False)
    op.create_index(op.f('ix_ai_usage_log_operation_type'), 'ai_usage_log', ['operation_type'], unique=False)
    op.create_index(op.f('ix_ai_usage_log_created_at'), 'ai_usage_log', ['created_at'], unique=False)

    # Create AI Usage Quota table
    op.create_table(
        'ai_usage_quota',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('monthly_ocr_limit', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('monthly_chat_limit', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('monthly_audit_limit', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('current_month', sa.String(), nullable=False),
        sa.Column('current_ocr_usage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_chat_usage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_audit_usage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('plan_tier', sa.String(), nullable=False, server_default='free'),
        sa.Column('is_unlimited', sa.String(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['company.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id')
    )
    op.create_index(op.f('ix_ai_usage_quota_company_id'), 'ai_usage_quota', ['company_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_usage_quota_company_id'), table_name='ai_usage_quota')
    op.drop_table('ai_usage_quota')
    op.drop_index(op.f('ix_ai_usage_log_created_at'), table_name='ai_usage_log')
    op.drop_index(op.f('ix_ai_usage_log_operation_type'), table_name='ai_usage_log')
    op.drop_index(op.f('ix_ai_usage_log_user_id'), table_name='ai_usage_log')
    op.drop_index(op.f('ix_ai_usage_log_company_id'), table_name='ai_usage_log')
    op.drop_table('ai_usage_log')
