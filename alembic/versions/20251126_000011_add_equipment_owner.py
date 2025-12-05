"""Add owner_id to equipment for owner-operators.

Revision ID: 20251126_000011
Revises: 20251126_000010
Create Date: 2025-11-26

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251126_000011'
down_revision = '20251126_000010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add owner_id to fleet_equipment
    op.add_column('fleet_equipment', sa.Column('owner_id', sa.String(), nullable=True))
    op.create_foreign_key('fk_fleet_equipment_owner', 'fleet_equipment', 'worker', ['owner_id'], ['id'])
    op.create_index(op.f('ix_fleet_equipment_owner_id'), 'fleet_equipment', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_fleet_equipment_owner_id'), table_name='fleet_equipment')
    op.drop_constraint('fk_fleet_equipment_owner', 'fleet_equipment', type_='foreignkey')
    op.drop_column('fleet_equipment', 'owner_id')
