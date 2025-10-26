"""Add multi-location management tables

Revision ID: 008_add_multi_location_tables
Revises: 007_add_collaboration_tables
Create Date: 2024-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008_add_multi_location_tables'
down_revision = '007_add_collaboration_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add multi-location management tables"""
    
    # CompanyLocations table for managing multiple company locations
    op.create_table('company_locations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('location_name', sa.String(), nullable=False),
        sa.Column('location_type', sa.String(), nullable=False),  # headquarters, terminal, warehouse, office
        sa.Column('address', sa.String(), nullable=False),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('zip_code', sa.String(), nullable=False),
        sa.Column('country', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('contact_person', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # LocationUsers table for managing users assigned to specific locations
    op.create_table('location_users',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('location_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),  # manager, dispatcher, driver, admin
        sa.Column('is_primary_location', sa.Boolean(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('assigned_by', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # LocationEquipment table for tracking equipment at each location
    op.create_table('location_equipment',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('location_id', sa.String(), nullable=False),
        sa.Column('equipment_type', sa.String(), nullable=False),  # truck, trailer, forklift, crane
        sa.Column('equipment_id', sa.String(), nullable=False),
        sa.Column('equipment_name', sa.String(), nullable=False),
        sa.Column('current_status', sa.String(), nullable=False),  # available, in_use, maintenance, out_of_service
        sa.Column('last_inspection', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_inspection', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('assigned_by', sa.String(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # InterLocationTransfers table for tracking transfers between locations
    op.create_table('inter_location_transfers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('transfer_type', sa.String(), nullable=False),  # equipment, driver, load
        sa.Column('item_id', sa.String(), nullable=False),
        sa.Column('from_location_id', sa.String(), nullable=False),
        sa.Column('to_location_id', sa.String(), nullable=False),
        sa.Column('transfer_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('estimated_arrival', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_arrival', sa.DateTime(timezone=True), nullable=True),
        sa.Column('transfer_reason', sa.String(), nullable=False),
        sa.Column('authorized_by', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),  # pending, in_transit, completed, cancelled
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # LocationFinancials table for tracking financial data per location
    op.create_table('location_financials',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('location_id', sa.String(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revenue', sa.Numeric(), nullable=False),
        sa.Column('expenses', sa.Numeric(), nullable=False),
        sa.Column('profit', sa.Numeric(), nullable=False),
        sa.Column('load_count', sa.Integer(), nullable=False),
        sa.Column('driver_count', sa.Integer(), nullable=False),
        sa.Column('equipment_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_company_locations_company', 'company_locations', ['company_id'])
    op.create_index('idx_company_locations_type', 'company_locations', ['location_type'])
    op.create_index('idx_company_locations_active', 'company_locations', ['is_active'])
    op.create_index('idx_company_locations_primary', 'company_locations', ['is_primary'])
    
    op.create_index('idx_location_users_location', 'location_users', ['location_id'])
    op.create_index('idx_location_users_user', 'location_users', ['user_id'])
    op.create_index('idx_location_users_role', 'location_users', ['role'])
    op.create_index('idx_location_users_active', 'location_users', ['is_active'])
    
    op.create_index('idx_location_equipment_location', 'location_equipment', ['location_id'])
    op.create_index('idx_location_equipment_type', 'location_equipment', ['equipment_type'])
    op.create_index('idx_location_equipment_status', 'location_equipment', ['current_status'])
    op.create_index('idx_location_equipment_active', 'location_equipment', ['is_active'])
    
    op.create_index('idx_inter_location_transfers_company', 'inter_location_transfers', ['company_id'])
    op.create_index('idx_inter_location_transfers_type', 'inter_location_transfers', ['transfer_type'])
    op.create_index('idx_inter_location_transfers_from', 'inter_location_transfers', ['from_location_id'])
    op.create_index('idx_inter_location_transfers_to', 'inter_location_transfers', ['to_location_id'])
    op.create_index('idx_inter_location_transfers_status', 'inter_location_transfers', ['status'])
    
    op.create_index('idx_location_financials_location', 'location_financials', ['location_id'])
    op.create_index('idx_location_financials_period', 'location_financials', ['period_start', 'period_end'])


def downgrade():
    """Remove multi-location management tables"""
    
    # Drop indexes
    op.drop_index('idx_location_financials_period', 'location_financials')
    op.drop_index('idx_location_financials_location', 'location_financials')
    
    op.drop_index('idx_inter_location_transfers_status', 'inter_location_transfers')
    op.drop_index('idx_inter_location_transfers_to', 'inter_location_transfers')
    op.drop_index('idx_inter_location_transfers_from', 'inter_location_transfers')
    op.drop_index('idx_inter_location_transfers_type', 'inter_location_transfers')
    op.drop_index('idx_inter_location_transfers_company', 'inter_location_transfers')
    
    op.drop_index('idx_location_equipment_active', 'location_equipment')
    op.drop_index('idx_location_equipment_status', 'location_equipment')
    op.drop_index('idx_location_equipment_type', 'location_equipment')
    op.drop_index('idx_location_equipment_location', 'location_equipment')
    
    op.drop_index('idx_location_users_active', 'location_users')
    op.drop_index('idx_location_users_role', 'location_users')
    op.drop_index('idx_location_users_user', 'location_users')
    op.drop_index('idx_location_users_location', 'location_users')
    
    op.drop_index('idx_company_locations_primary', 'company_locations')
    op.drop_index('idx_company_locations_active', 'company_locations')
    op.drop_index('idx_company_locations_type', 'company_locations')
    op.drop_index('idx_company_locations_company', 'company_locations')
    
    # Drop tables
    op.drop_table('location_financials')
    op.drop_table('inter_location_transfers')
    op.drop_table('location_equipment')
    op.drop_table('location_users')
    op.drop_table('company_locations')
