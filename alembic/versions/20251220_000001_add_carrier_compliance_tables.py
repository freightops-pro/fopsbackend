"""Add carrier compliance tables

Revision ID: 20251220_000001
Revises: 20251219_000001
Create Date: 2025-12-20 10:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20251220_000001"
down_revision = "20251219_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Company Insurance table
    op.create_table(
        "company_insurance",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("insurance_type", sa.String(), nullable=False),
        sa.Column("carrier_name", sa.String(), nullable=False),
        sa.Column("policy_number", sa.String(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("coverage_limit", sa.Numeric(14, 2), nullable=False),
        sa.Column("deductible", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="COMPLIANT"),
        sa.Column("certificate_holder", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_insurance_company_id", "company_insurance", ["company_id"])
    op.create_index("ix_company_insurance_expiration_date", "company_insurance", ["expiration_date"])

    # Carrier Credential table
    op.create_table(
        "carrier_credential",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("credential_type", sa.String(), nullable=False),
        sa.Column("credential_number", sa.String(), nullable=False),
        sa.Column("issuing_authority", sa.String(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="COMPLIANT"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carrier_credential_company_id", "carrier_credential", ["company_id"])

    # Vehicle Registration table
    op.create_table(
        "vehicle_registration",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("equipment_id", sa.String(), nullable=False),
        sa.Column("unit_number", sa.String(), nullable=False),
        sa.Column("plate_number", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("registration_type", sa.String(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="COMPLIANT"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicle_registration_company_id", "vehicle_registration", ["company_id"])
    op.create_index("ix_vehicle_registration_equipment_id", "vehicle_registration", ["equipment_id"])
    op.create_index("ix_vehicle_registration_expiration_date", "vehicle_registration", ["expiration_date"])

    # ELD Audit Item table
    op.create_table(
        "eld_audit_item",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False, server_default="MEDIUM"),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=True),
        sa.Column("driver_name", sa.String(), nullable=True),
        sa.Column("equipment_id", sa.String(), nullable=True),
        sa.Column("unit_number", sa.String(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="OPEN"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eld_audit_item_company_id", "eld_audit_item", ["company_id"])
    op.create_index("ix_eld_audit_item_driver_id", "eld_audit_item", ["driver_id"])
    op.create_index("ix_eld_audit_item_equipment_id", "eld_audit_item", ["equipment_id"])
    op.create_index("ix_eld_audit_item_status", "eld_audit_item", ["status"])

    # CSA Score table
    op.create_table(
        "csa_score",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("percentile", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="OK"),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("data_source", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_csa_score_company_id", "csa_score", ["company_id"])
    op.create_index("ix_csa_score_category", "csa_score", ["category"])

    # Carrier SAFER Snapshot table
    op.create_table(
        "carrier_safer_snapshot",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False),
        sa.Column("usdot_number", sa.String(), nullable=False),
        sa.Column("mc_number", sa.String(), nullable=True),
        sa.Column("legal_name", sa.String(), nullable=False),
        sa.Column("dba_name", sa.String(), nullable=True),
        sa.Column("physical_address", sa.String(), nullable=True),
        sa.Column("mailing_address", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("power_units", sa.Integer(), nullable=True),
        sa.Column("drivers", sa.Integer(), nullable=True),
        sa.Column("operating_status", sa.String(), nullable=False),
        sa.Column("mcs150_date", sa.Date(), nullable=True),
        sa.Column("out_of_service_date", sa.Date(), nullable=True),
        sa.Column("carrier_operation", sa.String(), nullable=True),
        sa.Column("cargo_carried", sa.String(), nullable=True),
        sa.Column("safety_rating", sa.String(), nullable=True),
        sa.Column("safety_rating_date", sa.Date(), nullable=True),
        sa.Column("last_fetched", sa.DateTime(), nullable=True),
        sa.Column("fetch_source", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carrier_safer_snapshot_company_id", "carrier_safer_snapshot", ["company_id"])
    op.create_index("ix_carrier_safer_snapshot_usdot_number", "carrier_safer_snapshot", ["usdot_number"])


def downgrade() -> None:
    op.drop_index("ix_carrier_safer_snapshot_usdot_number", table_name="carrier_safer_snapshot")
    op.drop_index("ix_carrier_safer_snapshot_company_id", table_name="carrier_safer_snapshot")
    op.drop_table("carrier_safer_snapshot")

    op.drop_index("ix_csa_score_category", table_name="csa_score")
    op.drop_index("ix_csa_score_company_id", table_name="csa_score")
    op.drop_table("csa_score")

    op.drop_index("ix_eld_audit_item_status", table_name="eld_audit_item")
    op.drop_index("ix_eld_audit_item_equipment_id", table_name="eld_audit_item")
    op.drop_index("ix_eld_audit_item_driver_id", table_name="eld_audit_item")
    op.drop_index("ix_eld_audit_item_company_id", table_name="eld_audit_item")
    op.drop_table("eld_audit_item")

    op.drop_index("ix_vehicle_registration_expiration_date", table_name="vehicle_registration")
    op.drop_index("ix_vehicle_registration_equipment_id", table_name="vehicle_registration")
    op.drop_index("ix_vehicle_registration_company_id", table_name="vehicle_registration")
    op.drop_table("vehicle_registration")

    op.drop_index("ix_carrier_credential_company_id", table_name="carrier_credential")
    op.drop_table("carrier_credential")

    op.drop_index("ix_company_insurance_expiration_date", table_name="company_insurance")
    op.drop_index("ix_company_insurance_company_id", table_name="company_insurance")
    op.drop_table("company_insurance")
