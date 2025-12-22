"""add_lat_lng_to_load_stop

Revision ID: c163090b4da8
Revises: 20251220_000001
Create Date: 2025-12-22 00:44:47.281293

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c163090b4da8'
down_revision = '20251220_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lat/lng columns to freight_load_stop for map display
    op.add_column('freight_load_stop', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('freight_load_stop', sa.Column('lng', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('freight_load_stop', 'lng')
    op.drop_column('freight_load_stop', 'lat')
