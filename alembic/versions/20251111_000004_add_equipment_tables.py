"""Add fleet equipment tables

Revision ID: 20251111_000004
Revises: 20251111_000003
Create Date: 2025-11-12 00:15:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20251111_000004"
down_revision = "20251111_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fleet_equipment",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("unit_number", sa.String(), nullable=False),
        sa.Column("equipment_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("operational_status", sa.String(), nullable=True),
        sa.Column("make", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("vin", sa.String(), nullable=True),
        sa.Column("current_mileage", sa.Integer(), nullable=True),
        sa.Column("current_engine_hours", sa.Float(), nullable=True),
        sa.Column("gps_provider", sa.String(), nullable=True),
        sa.Column("gps_device_id", sa.String(), nullable=True),
        sa.Column("eld_provider", sa.String(), nullable=True),
        sa.Column("eld_device_id", sa.String(), nullable=True),
        sa.Column("assigned_driver_id", sa.String(), nullable=True),
        sa.Column("assigned_truck_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fleet_equipment_company_id",
        "fleet_equipment",
        ["company_id"],
    )

    op.create_table(
        "fleet_equipment_usage",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("equipment_id", sa.String(), sa.ForeignKey("fleet_equipment.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("odometer", sa.Integer(), nullable=True),
        sa.Column("engine_hours", sa.Float(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fleet_equipment_usage_company_id",
        "fleet_equipment_usage",
        ["company_id"],
    )
    op.create_index(
        "ix_fleet_equipment_usage_equipment_id",
        "fleet_equipment_usage",
        ["equipment_id"],
    )

    op.create_table(
        "fleet_equipment_maintenance",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("equipment_id", sa.String(), sa.ForeignKey("fleet_equipment.id"), nullable=False),
        sa.Column("service_type", sa.String(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("vendor", sa.String(), nullable=True),
        sa.Column("odometer", sa.Integer(), nullable=True),
        sa.Column("engine_hours", sa.Float(), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("next_due_mileage", sa.Integer(), nullable=True),
        sa.Column("invoice_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fleet_equipment_maintenance_company_id",
        "fleet_equipment_maintenance",
        ["company_id"],
    )
    op.create_index(
        "ix_fleet_equipment_maintenance_equipment_id",
        "fleet_equipment_maintenance",
        ["equipment_id"],
    )

    op.create_table(
        "fleet_maintenance_forecast",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("equipment_id", sa.String(), sa.ForeignKey("fleet_equipment.id"), nullable=False),
        sa.Column("basis_event_id", sa.String(), sa.ForeignKey("fleet_equipment_maintenance.id"), nullable=True),
        sa.Column("service_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("projected_service_date", sa.Date(), nullable=True),
        sa.Column("projected_service_mileage", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fleet_maintenance_forecast_company_id",
        "fleet_maintenance_forecast",
        ["company_id"],
    )
    op.create_index(
        "ix_fleet_maintenance_forecast_equipment_id",
        "fleet_maintenance_forecast",
        ["equipment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_fleet_maintenance_forecast_equipment_id", table_name="fleet_maintenance_forecast")
    op.drop_index("ix_fleet_maintenance_forecast_company_id", table_name="fleet_maintenance_forecast")
    op.drop_table("fleet_maintenance_forecast")

    op.drop_index("ix_fleet_equipment_maintenance_equipment_id", table_name="fleet_equipment_maintenance")
    op.drop_index("ix_fleet_equipment_maintenance_company_id", table_name="fleet_equipment_maintenance")
    op.drop_table("fleet_equipment_maintenance")

    op.drop_index("ix_fleet_equipment_usage_equipment_id", table_name="fleet_equipment_usage")
    op.drop_index("ix_fleet_equipment_usage_company_id", table_name="fleet_equipment_usage")
    op.drop_table("fleet_equipment_usage")

    op.drop_index("ix_fleet_equipment_company_id", table_name="fleet_equipment")
    op.drop_table("fleet_equipment")

