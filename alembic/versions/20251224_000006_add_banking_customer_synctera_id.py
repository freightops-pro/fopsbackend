"""Add synctera_business_id to banking_customer table

Revision ID: 20251224_000006
Revises: 20251224_000005
Create Date: 2025-12-24 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251224_000006"
down_revision: Union[str, None] = "20251224_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add synctera_business_id column to banking_customer
    op.add_column(
        "banking_customer",
        sa.Column("synctera_business_id", sa.String(), nullable=True)
    )
    # Add unique constraint and index
    op.create_index(
        "ix_banking_customer_synctera_business_id",
        "banking_customer",
        ["synctera_business_id"],
        unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_banking_customer_synctera_business_id", table_name="banking_customer")
    op.drop_column("banking_customer", "synctera_business_id")
