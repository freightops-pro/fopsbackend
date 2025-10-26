"""Add driver WebSocket and location tracking tables

Revision ID: 009_add_driver_websocket_tables
Revises: 008_add_multi_location_tables
Create Date: 2024-01-20 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009_add_driver_websocket_tables'
down_revision = '008_add_multi_location_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add driver WebSocket and location tracking tables"""
    
    # DriverLocationHistory table for tracking driver GPS history
    op.create_table('driver_location_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=False),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('heading', sa.Float(), nullable=True),
        sa.Column('altitude', sa.Float(), nullable=True),
        sa.Column('is_moving', sa.Boolean(), nullable=False),
        sa.Column('is_on_duty', sa.Boolean(), nullable=False),
        sa.Column('load_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # DriverConnectionLog table for tracking WebSocket connections
    op.create_table('driver_connection_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('driver_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connection_type', sa.String(), nullable=False),  # websocket, rest_api
        sa.Column('device_info', postgresql.JSON(), nullable=True),
        sa.Column('app_version', sa.String(), nullable=True),
        sa.Column('session_duration', sa.Integer(), nullable=True),  # seconds
        sa.Column('disconnect_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_driver_location_timestamp', 'driver_location_history', ['driver_id', 'timestamp'])
    op.create_index('idx_driver_location_company', 'driver_location_history', ['company_id', 'timestamp'])
    op.create_index('idx_driver_location_load', 'driver_location_history', ['load_id', 'timestamp'])
    
    op.create_index('idx_driver_connection_driver', 'driver_connection_logs', ['driver_id'])
    op.create_index('idx_driver_connection_company', 'driver_connection_logs', ['company_id'])
    op.create_index('idx_driver_connection_connected', 'driver_connection_logs', ['connected_at'])
    op.create_index('idx_driver_connection_type', 'driver_connection_logs', ['connection_type'])


def downgrade():
    """Remove driver WebSocket and location tracking tables"""
    
    # Drop indexes
    op.drop_index('idx_driver_connection_type', 'driver_connection_logs')
    op.drop_index('idx_driver_connection_connected', 'driver_connection_logs')
    op.drop_index('idx_driver_connection_company', 'driver_connection_logs')
    op.drop_index('idx_driver_connection_driver', 'driver_connection_logs')
    
    op.drop_index('idx_driver_location_load', 'driver_location_history')
    op.drop_index('idx_driver_location_company', 'driver_location_history')
    op.drop_index('idx_driver_location_timestamp', 'driver_location_history')
    
    # Drop tables
    op.drop_table('driver_connection_logs')
    op.drop_table('driver_location_history')
