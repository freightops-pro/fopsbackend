"""Add setup_fee to hq_tenant table

Revision ID: 20251224_000005
Revises: 20251224_000004
Create Date: 2025-12-24 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251224_000005"
down_revision: Union[str, None] = "20251224_000004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hq_tenant", sa.Column("setup_fee", sa.Numeric(10, 2), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("hq_tenant", "setup_fee")
