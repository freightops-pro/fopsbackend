"""add_delivery_flow_fields_to_simple_loads

Revision ID: 85fd3596193e
Revises: 811bf06e0056
Create Date: 2025-09-28 15:21:56.948437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85fd3596193e'
down_revision: Union[str, None] = '811bf06e0056'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add delivery flow fields to simple_loads table
    op.add_column('simple_loads', sa.Column('deliveryStatus', sa.String(50), nullable=True, server_default='in_transit'))
    op.add_column('simple_loads', sa.Column('arrivalTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('dockingTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('unloadingStartTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('unloadingEndTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('deliveryTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('proofOfDeliveryUrl', sa.String(500), nullable=True))
    op.add_column('simple_loads', sa.Column('recipientName', sa.String(255), nullable=True))
    op.add_column('simple_loads', sa.Column('deliveryNotes', sa.String(1000), nullable=True))


def downgrade() -> None:
    # Remove delivery flow fields from simple_loads table
    op.drop_column('simple_loads', 'deliveryNotes')
    op.drop_column('simple_loads', 'recipientName')
    op.drop_column('simple_loads', 'proofOfDeliveryUrl')
    op.drop_column('simple_loads', 'deliveryTime')
    op.drop_column('simple_loads', 'unloadingEndTime')
    op.drop_column('simple_loads', 'unloadingStartTime')
    op.drop_column('simple_loads', 'dockingTime')
    op.drop_column('simple_loads', 'arrivalTime')
    op.drop_column('simple_loads', 'deliveryStatus')
