"""Fix hq_employee columns - Add missing referral_code_generated_at and commission rate columns

Revision ID: 20260114_hq_employee_fix
Revises: 20260112_master_spec
Create Date: 2026-01-14

This migration fixes the mismatch between the HQEmployee model and database:
- Adds missing referral_code_generated_at column
- Adds granular commission rate columns (mrr, setup, fintech)
- Renames total_referrals to lifetime_referrals
- Renames total_commission_earned to lifetime_commission_earned
- Removes is_affiliate column (not in model)
- Removes single commission_rate column (replaced by 3 separate columns)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260114_hq_employee_fix'
down_revision = '20260112_master_spec'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing referral_code_generated_at column
    op.add_column('hq_employee', sa.Column(
        'referral_code_generated_at',
        sa.DateTime(),
        nullable=True,
        comment='Master Spec: When referral code was generated'
    ))

    # Add granular commission rate columns
    op.add_column('hq_employee', sa.Column(
        'commission_rate_mrr',
        sa.Numeric(5, 4),
        nullable=True,
        comment='Master Spec: Commission % on MRR (e.g., 0.1000 = 10%)'
    ))

    op.add_column('hq_employee', sa.Column(
        'commission_rate_setup',
        sa.Numeric(5, 4),
        nullable=True,
        comment='Master Spec: Commission % on setup fees'
    ))

    op.add_column('hq_employee', sa.Column(
        'commission_rate_fintech',
        sa.Numeric(5, 4),
        nullable=True,
        comment='Master Spec: Commission % on fintech revenue'
    ))

    # Add performance metrics columns
    op.add_column('hq_employee', sa.Column(
        'lifetime_referrals',
        sa.Integer(),
        nullable=True,
        server_default='0',
        comment='Master Spec: Total tenants referred by this agent'
    ))

    op.add_column('hq_employee', sa.Column(
        'lifetime_commission_earned',
        sa.Numeric(12, 2),
        nullable=True,
        server_default='0',
        comment='Master Spec: Total commissions earned'
    ))

    # Migrate data from old columns to new columns
    op.execute("""
        UPDATE hq_employee
        SET lifetime_referrals = COALESCE(total_referrals, 0),
            lifetime_commission_earned = COALESCE(total_commission_earned, 0)
        WHERE total_referrals IS NOT NULL OR total_commission_earned IS NOT NULL
    """)

    # Drop old columns that don't match model
    op.drop_column('hq_employee', 'total_referrals')
    op.drop_column('hq_employee', 'total_commission_earned')
    op.drop_column('hq_employee', 'is_affiliate')
    op.drop_column('hq_employee', 'commission_rate')


def downgrade() -> None:
    # Restore old columns
    op.add_column('hq_employee', sa.Column('commission_rate', sa.Numeric(5, 2), nullable=True, server_default='10'))
    op.add_column('hq_employee', sa.Column('is_affiliate', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('hq_employee', sa.Column('total_referrals', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('hq_employee', sa.Column('total_commission_earned', sa.Numeric(12, 2), nullable=True, server_default='0'))

    # Migrate data back
    op.execute("""
        UPDATE hq_employee
        SET total_referrals = COALESCE(lifetime_referrals, 0),
            total_commission_earned = COALESCE(lifetime_commission_earned, 0)
        WHERE lifetime_referrals IS NOT NULL OR lifetime_commission_earned IS NOT NULL
    """)

    # Drop new columns
    op.drop_column('hq_employee', 'lifetime_commission_earned')
    op.drop_column('hq_employee', 'lifetime_referrals')
    op.drop_column('hq_employee', 'commission_rate_fintech')
    op.drop_column('hq_employee', 'commission_rate_setup')
    op.drop_column('hq_employee', 'commission_rate_mrr')
    op.drop_column('hq_employee', 'referral_code_generated_at')
