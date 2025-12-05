"""add_equipment_unique_constraints

Revision ID: 752eb60d0550
Revises: 20251129_000013
Create Date: 2025-11-30 22:37:06.826504

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '752eb60d0550'
down_revision = '20251129_000013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint for unit_number within a company
    op.create_unique_constraint('uq_equipment_company_unit_number', 'fleet_equipment', ['company_id', 'unit_number'])

    # Add partial unique index for VIN - only when VIN is not null and not empty
    # This allows multiple equipment without VINs but prevents duplicate VINs
    op.execute(text("""
        CREATE UNIQUE INDEX uq_equipment_company_vin
        ON fleet_equipment (company_id, vin)
        WHERE vin IS NOT NULL AND vin != ''
    """))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS uq_equipment_company_vin"))
    op.drop_constraint('uq_equipment_company_unit_number', 'fleet_equipment', type_='unique')
