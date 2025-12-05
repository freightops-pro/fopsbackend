"""Initial core tables

Revision ID: 20251111_000001
Revises: 
Create Date: 2025-11-11 05:05:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251111_000001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("subscription_plan", sa.String(), nullable=False, server_default="pro"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "user",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="dispatcher"),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "driver",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("first_name", sa.String(), nullable=False),
        sa.Column("last_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("cdl_number", sa.String(), nullable=True),
        sa.Column("cdl_expiration", sa.Date(), nullable=True),
        sa.Column("medical_card_expiration", sa.Date(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "automationrule",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False, index=True),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("recipients", sa.JSON(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("threshold_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("escalation_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "driverincident",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=False, index=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("incident_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "drivertraining",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=False, index=True),
        sa.Column("course_name", sa.String(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("instructor", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "driver_document",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=False, index=True),
        sa.Column("document_type", sa.String(), nullable=False),
        sa.Column("file_url", sa.String(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "fueltransaction",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=True, index=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("gallons", sa.Numeric(12, 3), nullable=False),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("fuel_card", sa.String(), nullable=True),
        sa.Column("metadata", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "jurisdictionrollup",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=False),
        sa.Column("gallons", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("taxable_gallons", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("miles", sa.Numeric(12, 1), nullable=False, server_default=sa.text("0")),
        sa.Column("tax_due", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("surcharge_due", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_trip_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "freight_load",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("customer_name", sa.String(), nullable=False),
        sa.Column("load_type", sa.String(), nullable=False),
        sa.Column("commodity", sa.String(), nullable=False),
        sa.Column("base_rate", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("container_number", sa.String(), nullable=True),
        sa.Column("container_size", sa.String(), nullable=True),
        sa.Column("container_type", sa.String(), nullable=True),
        sa.Column("vessel_name", sa.String(), nullable=True),
        sa.Column("voyage_number", sa.String(), nullable=True),
        sa.Column("origin_port_code", sa.String(), nullable=True),
        sa.Column("destination_port_code", sa.String(), nullable=True),
        sa.Column("drayage_appointment", sa.String(), nullable=True),
        sa.Column("customs_hold", sa.String(), nullable=True),
        sa.Column("customs_reference", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "freight_load_stop",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("load_id", sa.String(), sa.ForeignKey("freight_load.id"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stop_type", sa.String(), nullable=False),
        sa.Column("location_name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("postal_code", sa.String(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("instructions", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "accounting_invoice",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("load_id", sa.String(), sa.ForeignKey("freight_load.id"), nullable=True, index=True),
        sa.Column("invoice_number", sa.String(), nullable=False, unique=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_items", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "accounting_ledger_entry",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("load_id", sa.String(), sa.ForeignKey("freight_load.id"), nullable=True, index=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "accounting_settlement",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("driver_id", sa.String(), sa.ForeignKey("driver.id"), nullable=False, index=True),
        sa.Column("load_id", sa.String(), sa.ForeignKey("freight_load.id"), nullable=True, index=True),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        sa.Column("total_earnings", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(12, 2), nullable=False),
        sa.Column("net_pay", sa.Numeric(12, 2), nullable=False),
        sa.Column("breakdown", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "banking_customer",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("external_id", sa.String(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "banking_account",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(), sa.ForeignKey("banking_customer.id"), nullable=False, index=True),
        sa.Column("account_type", sa.String(), nullable=False),
        sa.Column("nickname", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(), nullable=False, server_default="inactive"),
        sa.Column("external_id", sa.String(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "banking_card",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), sa.ForeignKey("banking_account.id"), nullable=False, index=True),
        sa.Column("cardholder_name", sa.String(), nullable=False),
        sa.Column("last_four", sa.String(), nullable=False),
        sa.Column("card_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="inactive"),
        sa.Column("expiration_month", sa.String(), nullable=True),
        sa.Column("expiration_year", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "banking_transaction",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), sa.ForeignKey("banking_account.id"), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False, server_default="USD"),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False, server_default="general"),
        sa.Column("posted_at", sa.DateTime(), nullable=False),
        sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("external_id", sa.String(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "collab_channel",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "collab_message",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("channel_id", sa.String(), sa.ForeignKey("collab_channel.id"), nullable=False, index=True),
        sa.Column("author_id", sa.String(), sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "collab_presence",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("channel_id", sa.String(), sa.ForeignKey("collab_channel.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("user.id"), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="online"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_table(
        "notificationlog",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("rule_id", sa.String(), sa.ForeignKey("automationrule.id"), nullable=False, index=True),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("recipient", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="sent"),
        sa.Column("detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

