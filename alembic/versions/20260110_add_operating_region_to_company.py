"""add operating_region to company

Revision ID: 20260110_000001
Revises: 076f00c0a1a2
Create Date: 2026-01-10 23:36:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = '20260110_000001'
down_revision = '076f00c0a1a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add operating_region column with default value
    op.add_column('company', sa.Column('operating_region', sa.String(), nullable=True, server_default='usa'))

    # Add regional_data column with default empty JSON object
    op.add_column('company', sa.Column('regional_data', JSONB, nullable=True, server_default='{}'))


def downgrade() -> None:
    # Remove the columns
    op.drop_column('company', 'regional_data')
    op.drop_column('company', 'operating_region')
