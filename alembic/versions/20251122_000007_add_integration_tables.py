"""Add integration tables

Revision ID: 20251122_000007
Revises: 20251120_000007
Create Date: 2025-11-22 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251122_000007"
down_revision: Union[str, None] = "20251120_000007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create integration catalog table
    op.create_table(
        "integration",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("integration_key", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("integration_type", sa.String(), nullable=False, index=True),
        sa.Column("auth_type", sa.String(), nullable=False),
        sa.Column("requires_oauth", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("support_email", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create company_integration table
    op.create_table(
        "company_integration",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("integration_id", sa.String(), sa.ForeignKey("integration.id"), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, server_default="not-activated"),
        sa.Column("credentials", sa.JSON(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("auto_sync", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("company_integration")
    op.drop_table("integration")









