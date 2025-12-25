"""Add FMCSA fields to hq_lead table

Revision ID: 20251225_fmcsa
Revises: 20251225_lead_act
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251225_fmcsa'
down_revision: Union[str, None] = '20251225_lead_act'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add FMCSA-specific fields to hq_lead table
    op.add_column('hq_lead', sa.Column('state', sa.String(2), nullable=True))
    op.add_column('hq_lead', sa.Column('dot_number', sa.String(50), nullable=True))
    op.add_column('hq_lead', sa.Column('mc_number', sa.String(50), nullable=True))
    op.add_column('hq_lead', sa.Column('carrier_type', sa.String(100), nullable=True))
    op.add_column('hq_lead', sa.Column('cargo_types', sa.String(500), nullable=True))

    # Add indexes for FMCSA lookup
    op.create_index('ix_hq_lead_state', 'hq_lead', ['state'])
    op.create_index('ix_hq_lead_dot_number', 'hq_lead', ['dot_number'])
    op.create_index('ix_hq_lead_mc_number', 'hq_lead', ['mc_number'])

    # Add 'fmcsa' to the lead source enum if it doesn't exist
    # Note: PostgreSQL enum modification - this is a safe operation
    op.execute("ALTER TYPE leadsource ADD VALUE IF NOT EXISTS 'fmcsa'")


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_hq_lead_mc_number', 'hq_lead')
    op.drop_index('ix_hq_lead_dot_number', 'hq_lead')
    op.drop_index('ix_hq_lead_state', 'hq_lead')

    # Remove columns
    op.drop_column('hq_lead', 'cargo_types')
    op.drop_column('hq_lead', 'carrier_type')
    op.drop_column('hq_lead', 'mc_number')
    op.drop_column('hq_lead', 'dot_number')
    op.drop_column('hq_lead', 'state')
