"""add_truck_assignment_fields

Revision ID: 3f26c54b5f2a
Revises: fed75f48fafa
Create Date: 2025-09-28 17:50:39.951565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f26c54b5f2a'
down_revision: Union[str, None] = 'fed75f48fafa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add truck assignment flow fields to simple_loads table
    op.add_column('simple_loads', sa.Column('truckAssignmentStatus', sa.String(50), nullable=True, server_default='truck_assignment_required'))
    op.add_column('simple_loads', sa.Column('truckAssignmentTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('driverConfirmationTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('trailerSetupTime', sa.DateTime(), nullable=True))
    op.add_column('simple_loads', sa.Column('truckConfirmationTime', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove truck assignment flow fields from simple_loads table
    op.drop_column('simple_loads', 'truckConfirmationTime')
    op.drop_column('simple_loads', 'trailerSetupTime')
    op.drop_column('simple_loads', 'driverConfirmationTime')
    op.drop_column('simple_loads', 'truckAssignmentTime')
    op.drop_column('simple_loads', 'truckAssignmentStatus')
