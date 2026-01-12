"""Merge hq_deal_fix and main branches

Revision ID: a65a68d3ee84
Revises: 20260110_000001, 20260112_fix_deal_schema
Create Date: 2026-01-11 21:30:22.055425

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a65a68d3ee84'
down_revision = ('20260110_000001', '20260112_fix_deal_schema')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

