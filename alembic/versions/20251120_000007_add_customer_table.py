"""Add accounting_customer table

Revision ID: 20251120_000007
Revises: 20251112_000006
Create Date: 2025-11-20 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251120_000007"
down_revision: Union[str, None] = "20251112_000006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "accounting_customer",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        
        # Basic Info
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("legal_name", sa.String(), nullable=True),
        sa.Column("tax_id", sa.String(), nullable=True),
        
        # Contact Info
        sa.Column("primary_contact_name", sa.String(), nullable=True),
        sa.Column("primary_contact_email", sa.String(), nullable=True),
        sa.Column("primary_contact_phone", sa.String(), nullable=True),
        
        # Addresses (stored as JSON)
        sa.Column("billing_address", sa.JSON(), nullable=True),
        sa.Column("shipping_address", sa.JSON(), nullable=True),
        
        # Payment Terms
        sa.Column("payment_terms", sa.String(), nullable=True),
        sa.Column("credit_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("credit_limit_used", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        
        # Banking Integration
        sa.Column("synctera_account_id", sa.String(), nullable=True),
        
        # Status
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        
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
    op.drop_table("accounting_customer")

