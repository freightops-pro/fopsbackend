"""add_worker_id_to_driver

Revision ID: e9f31e598fb6
Revises: 20251126_000011
Create Date: 2025-11-27 22:16:56.972270

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9f31e598fb6'
down_revision = '20251126_000011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add worker_id column to driver table
    op.add_column('driver', sa.Column('worker_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_driver_worker_id'), 'driver', ['worker_id'], unique=False)
    op.create_foreign_key('fk_driver_worker_id', 'driver', 'worker', ['worker_id'], ['id'])


def downgrade() -> None:
    # Remove worker_id column from driver table
    op.drop_constraint('fk_driver_worker_id', 'driver', type_='foreignkey')
    op.drop_index(op.f('ix_driver_worker_id'), table_name='driver')
    op.drop_column('driver', 'worker_id')

