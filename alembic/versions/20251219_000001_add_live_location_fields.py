"""Add live location tracking fields to equipment and profile fields to users/companies

Revision ID: 20251219_000001
Revises: 20251218_000001_add_rbac_tables
Create Date: 2025-12-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251219_000001'
down_revision = '20251218_000001_add_rbac_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add live location tracking fields to fleet_equipment
    op.add_column('fleet_equipment', sa.Column('current_lat', sa.Float(), nullable=True))
    op.add_column('fleet_equipment', sa.Column('current_lng', sa.Float(), nullable=True))
    op.add_column('fleet_equipment', sa.Column('current_city', sa.String(), nullable=True))
    op.add_column('fleet_equipment', sa.Column('current_state', sa.String(), nullable=True))
    op.add_column('fleet_equipment', sa.Column('last_location_update', sa.DateTime(), nullable=True))
    op.add_column('fleet_equipment', sa.Column('heading', sa.Float(), nullable=True))
    op.add_column('fleet_equipment', sa.Column('speed_mph', sa.Float(), nullable=True))

    # Add user profile fields
    op.add_column('user', sa.Column('phone', sa.String(), nullable=True))
    op.add_column('user', sa.Column('avatar_url', sa.String(), nullable=True))
    op.add_column('user', sa.Column('timezone', sa.String(), nullable=True, server_default='America/Chicago'))
    op.add_column('user', sa.Column('job_title', sa.String(), nullable=True))

    # Add company profile fields
    op.add_column('company', sa.Column('legal_name', sa.String(), nullable=True))
    op.add_column('company', sa.Column('fax', sa.String(), nullable=True))
    op.add_column('company', sa.Column('tax_id', sa.String(), nullable=True))
    op.add_column('company', sa.Column('address_line1', sa.String(), nullable=True))
    op.add_column('company', sa.Column('address_line2', sa.String(), nullable=True))
    op.add_column('company', sa.Column('city', sa.String(), nullable=True))
    op.add_column('company', sa.Column('state', sa.String(), nullable=True))
    op.add_column('company', sa.Column('zip_code', sa.String(), nullable=True))
    op.add_column('company', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('company', sa.Column('website', sa.String(), nullable=True))
    op.add_column('company', sa.Column('year_founded', sa.String(), nullable=True))
    op.add_column('company', sa.Column('logo_url', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove company profile fields
    op.drop_column('company', 'logo_url')
    op.drop_column('company', 'year_founded')
    op.drop_column('company', 'website')
    op.drop_column('company', 'description')
    op.drop_column('company', 'zip_code')
    op.drop_column('company', 'state')
    op.drop_column('company', 'city')
    op.drop_column('company', 'address_line2')
    op.drop_column('company', 'address_line1')
    op.drop_column('company', 'tax_id')
    op.drop_column('company', 'fax')
    op.drop_column('company', 'legal_name')

    # Remove user profile fields
    op.drop_column('user', 'job_title')
    op.drop_column('user', 'timezone')
    op.drop_column('user', 'avatar_url')
    op.drop_column('user', 'phone')

    # Remove equipment location fields
    op.drop_column('fleet_equipment', 'speed_mph')
    op.drop_column('fleet_equipment', 'heading')
    op.drop_column('fleet_equipment', 'last_location_update')
    op.drop_column('fleet_equipment', 'current_state')
    op.drop_column('fleet_equipment', 'current_city')
    op.drop_column('fleet_equipment', 'current_lng')
    op.drop_column('fleet_equipment', 'current_lat')
