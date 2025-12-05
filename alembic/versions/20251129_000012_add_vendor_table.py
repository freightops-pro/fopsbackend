"""Add accounting_vendor table

Revision ID: 20251129_000012
Revises: 073c336be0eb
Create Date: 2025-11-29 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251129_000012"
down_revision: Union[str, None] = "073c336be0eb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounting_vendor",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),

        # Basic Info
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=True),
        sa.Column("tax_id", sa.String(), nullable=True),

        # Category
        sa.Column("category", sa.String(), nullable=False, server_default="equipment_maintenance"),

        # Contact Info
        sa.Column("primary_contact_name", sa.String(), nullable=True),
        sa.Column("primary_contact_email", sa.String(), nullable=True),
        sa.Column("primary_contact_phone", sa.String(), nullable=True),

        # Address (stored as JSON)
        sa.Column("address", sa.JSON(), nullable=True),

        # Payment Terms
        sa.Column("payment_terms", sa.String(), nullable=True),

        # Contract Info
        sa.Column("contract_start_date", sa.Date(), nullable=True),
        sa.Column("contract_end_date", sa.Date(), nullable=True),
        sa.Column("contract_value", sa.Numeric(12, 2), nullable=True),

        # Outstanding Balance
        sa.Column("outstanding_balance", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),

        # Status
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),

        # Notes
        sa.Column("notes", sa.String(), nullable=True),

        # Metadata
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


def downgrade() -> None:
    op.drop_table("accounting_vendor")
