"""Add location tracking fields to SimpleLoad

Revision ID: 006_add_location_tracking
Revises: 005_add_port_credential_system
Create Date: 2024-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006_add_location_tracking'
down_revision = '005_add_port_credential_system'
branch_labels = None
depends_on = None


def upgrade():
    """Add location tracking fields to SimpleLoad table"""
    
    # Add driver mobile location tracking fields
    op.add_column('simple_loads', sa.Column('current_driver_latitude', sa.Float(), nullable=True))
    op.add_column('simple_loads', sa.Column('current_driver_longitude', sa.Float(), nullable=True))
    op.add_column('simple_loads', sa.Column('last_location_update', sa.DateTime(), nullable=True))
    
    # Add pickup location verification fields
    op.add_column('simple_loads', sa.Column('actual_pickup_latitude', sa.Float(), nullable=True))
    op.add_column('simple_loads', sa.Column('actual_pickup_longitude', sa.Float(), nullable=True))
    op.add_column('simple_loads', sa.Column('actual_pickup_time', sa.DateTime(), nullable=True))
    
    # Add delivery location verification fields
    op.add_column('simple_loads', sa.Column('actual_delivery_latitude', sa.Float(), nullable=True))
    op.add_column('simple_loads', sa.Column('actual_delivery_longitude', sa.Float(), nullable=True))
    op.add_column('simple_loads', sa.Column('actual_delivery_time', sa.DateTime(), nullable=True))
    
    # Add route tracking field (JSON array of location points)
    op.add_column('simple_loads', sa.Column('route_history', postgresql.JSON(), nullable=True))
    
    # Create indexes for performance
    op.create_index('idx_simple_loads_location_update', 'simple_loads', ['last_location_update'])
    op.create_index('idx_simple_loads_pickup_verification', 'simple_loads', ['actual_pickup_time'])
    op.create_index('idx_simple_loads_delivery_verification', 'simple_loads', ['actual_delivery_time'])


def downgrade():
    """Remove location tracking fields from SimpleLoad table"""
    
    # Drop indexes
    op.drop_index('idx_simple_loads_delivery_verification', 'simple_loads')
    op.drop_index('idx_simple_loads_pickup_verification', 'simple_loads')
    op.drop_index('idx_simple_loads_location_update', 'simple_loads')
    
    # Drop columns
    op.drop_column('simple_loads', 'route_history')
    op.drop_column('simple_loads', 'actual_delivery_time')
    op.drop_column('simple_loads', 'actual_delivery_longitude')
    op.drop_column('simple_loads', 'actual_delivery_latitude')
    op.drop_column('simple_loads', 'actual_pickup_time')
    op.drop_column('simple_loads', 'actual_pickup_longitude')
    op.drop_column('simple_loads', 'actual_pickup_latitude')
    op.drop_column('simple_loads', 'last_location_update')
    op.drop_column('simple_loads', 'current_driver_longitude')
    op.drop_column('simple_loads', 'current_driver_latitude')
