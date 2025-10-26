"""add_pickup_flow_fields

Revision ID: fed75f48fafa
Revises: 85fd3596193e
Create Date: 2025-09-28 17:37:24.398752

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fed75f48fafa'
down_revision: Union[str, None] = '85fd3596193e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add pickup flow fields to simple_loads table
    op.add_column('simple_loads', sa.Column('pickupStatus', sa.String(50), nullable=True, server_default='pending'))
    op.add_column('simple_loads', sa.Column('navigationStartTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('pickupArrivalTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('trailerConfirmationTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('containerConfirmationTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('pickupConfirmationTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('departureTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('billOfLadingUrl', sa.String(500), nullable=True))
    op.add_column('simple_loads', sa.Column('pickupNotes', sa.String(1000), nullable=True))


def downgrade() -> None:
    # Remove pickup flow fields from simple_loads table
    op.drop_column('simple_loads', 'pickupNotes')
    op.drop_column('simple_loads', 'billOfLadingUrl')
    op.drop_column('simple_loads', 'departureTime')
    op.drop_column('simple_loads', 'pickupConfirmationTime')
    op.drop_column('simple_loads', 'containerConfirmationTime')
    op.drop_column('simple_loads', 'trailerConfirmationTime')
    op.drop_column('simple_loads', 'pickupArrivalTime')
    op.drop_column('simple_loads', 'navigationStartTime')
    op.drop_column('simple_loads', 'pickupStatus')
