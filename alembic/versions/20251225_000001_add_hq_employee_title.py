"""Add title column to hq_employee table

Revision ID: 20251225_000001
Revises: 20251224_000006
Create Date: 2025-12-25 06:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251225_000001"
down_revision: Union[str, None] = "20251224_000006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add title column to hq_employee (job title)
    op.add_column("hq_employee", sa.Column("title", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("hq_employee", "title")
