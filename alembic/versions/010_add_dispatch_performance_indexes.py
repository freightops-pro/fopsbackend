"""Add performance indexes for dispatch module

Revision ID: 010_dispatch_indexes
Revises: 009_add_driver_websocket_tables
Create Date: 2025-01-26 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_dispatch_indexes'
down_revision = '009_add_driver_websocket_tables'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add performance indexes for dispatch module queries.
    
    These indexes improve query performance for:
    - Multi-tenant isolation (company_id)
    - Load status filtering
    - Date range queries
    - Foreign key relationships
    """
    # Index on SimpleLoad for multi-tenant queries
    op.create_index(
        'idx_simple_loads_company_id',
        'simple_loads',
        ['companyId'],
        unique=False
    )
    
    # Compound index for status filtering within company
    op.create_index(
        'idx_simple_loads_company_status',
        'simple_loads',
        ['companyId', 'status'],
        unique=False
    )
    
    # Indexes for date range queries
    op.create_index(
        'idx_simple_loads_pickup_date',
        'simple_loads',
        ['pickupDate'],
        unique=False
    )
    
    op.create_index(
        'idx_simple_loads_delivery_date',
        'simple_loads',
        ['deliveryDate'],
        unique=False
    )
    
    # Compound index for company + pickup date queries
    op.create_index(
        'idx_simple_loads_company_pickup_date',
        'simple_loads',
        ['companyId', 'pickupDate'],
        unique=False
    )
    
    # Index for assigned driver lookups
    op.create_index(
        'idx_simple_loads_assigned_driver',
        'simple_loads',
        ['assignedDriverId'],
        unique=False
    )
    
    # Index for assigned truck lookups
    op.create_index(
        'idx_simple_loads_assigned_truck',
        'simple_loads',
        ['assignedTruckId'],
        unique=False
    )
    
    # LoadBilling indexes
    op.create_index(
        'idx_load_billing_load_id',
        'load_billing',
        ['load_id'],
        unique=False
    )
    
    op.create_index(
        'idx_load_billing_company_id',
        'load_billing',
        ['company_id'],
        unique=False
    )
    
    op.create_index(
        'idx_load_billing_company_status',
        'load_billing',
        ['company_id', 'billing_status'],
        unique=False
    )
    
    # LoadAccessorial indexes
    op.create_index(
        'idx_load_accessorial_load_id',
        'load_accessorials',
        ['load_id'],
        unique=False
    )
    
    op.create_index(
        'idx_load_accessorial_company_id',
        'load_accessorials',
        ['company_id'],
        unique=False
    )
    
    # LoadStop indexes for multi-leg queries
    op.create_index(
        'idx_load_stops_load_id',
        'load_stops',
        ['load_id'],
        unique=False
    )
    
    op.create_index(
        'idx_load_stops_sequence',
        'load_stops',
        ['load_id', 'sequence_number'],
        unique=False
    )
    
    # LoadLeg indexes for dispatch operations
    op.create_index(
        'idx_load_legs_company_id',
        'load_legs',
        ['company_id'],
        unique=False
    )
    
    op.create_index(
        'idx_load_legs_load_id',
        'load_legs',
        ['load_id'],
        unique=False
    )
    
    op.create_index(
        'idx_load_legs_driver_id',
        'load_legs',
        ['driver_id'],
        unique=False
    )
    
    op.create_index(
        'idx_load_legs_company_status',
        'load_legs',
        ['company_id', 'status'],
        unique=False
    )


def downgrade():
    """Remove all indexes created in upgrade."""
    # SimpleLoad indexes
    op.drop_index('idx_simple_loads_company_id', table_name='simple_loads')
    op.drop_index('idx_simple_loads_company_status', table_name='simple_loads')
    op.drop_index('idx_simple_loads_pickup_date', table_name='simple_loads')
    op.drop_index('idx_simple_loads_delivery_date', table_name='simple_loads')
    op.drop_index('idx_simple_loads_company_pickup_date', table_name='simple_loads')
    op.drop_index('idx_simple_loads_assigned_driver', table_name='simple_loads')
    op.drop_index('idx_simple_loads_assigned_truck', table_name='simple_loads')
    
    # LoadBilling indexes
    op.drop_index('idx_load_billing_load_id', table_name='load_billing')
    op.drop_index('idx_load_billing_company_id', table_name='load_billing')
    op.drop_index('idx_load_billing_company_status', table_name='load_billing')
    
    # LoadAccessorial indexes
    op.drop_index('idx_load_accessorial_load_id', table_name='load_accessorials')
    op.drop_index('idx_load_accessorial_company_id', table_name='load_accessorials')
    
    # LoadStop indexes
    op.drop_index('idx_load_stops_load_id', table_name='load_stops')
    op.drop_index('idx_load_stops_sequence', table_name='load_stops')
    
    # LoadLeg indexes
    op.drop_index('idx_load_legs_company_id', table_name='load_legs')
    op.drop_index('idx_load_legs_load_id', table_name='load_legs')
    op.drop_index('idx_load_legs_driver_id', table_name='load_legs')
    op.drop_index('idx_load_legs_company_status', table_name='load_legs')

