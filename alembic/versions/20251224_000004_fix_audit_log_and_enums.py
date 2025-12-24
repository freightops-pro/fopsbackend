"""Fix audit_log missing columns and journal entry enum

Revision ID: 20251224_000004
Revises: 20251224_000003
Create Date: 2025-12-24 14:15:00.000000

Adds missing columns to audit_log and fixes enum issues.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20251224_000004"
down_revision: Union[str, None] = "20251224_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to audit_log table
    op.add_column("audit_log", sa.Column("user_email", sa.String(), nullable=True))
    op.add_column("audit_log", sa.Column("request_id", sa.String(), nullable=True))
    op.add_column("audit_log", sa.Column("error_message", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_log", "error_message")
    op.drop_column("audit_log", "request_id")
    op.drop_column("audit_log", "user_email")
