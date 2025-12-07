"""Add phone_carrier to drivers for email-to-SMS notifications

Revision ID: 20251207_000001
Revises: 20251206_000001
Create Date: 2025-12-07 00:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20251207_000001"
down_revision = "20251206_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add phone_carrier column to driver table"""
    with op.batch_alter_table("driver") as batch_op:
        batch_op.add_column(
            sa.Column(
                "phone_carrier",
                sa.String(20),
                nullable=True,
                comment="Phone carrier for email-to-SMS notifications (verizon, att, tmobile, etc.)"
            )
        )

    # Create index for faster queries (only for non-SQLite databases)
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.create_index(
            "ix_driver_phone_carrier",
            "driver",
            ["phone_carrier"]
        )


def downgrade() -> None:
    """Remove phone_carrier column from driver table"""
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_index("ix_driver_phone_carrier", "driver")

    with op.batch_alter_table("driver") as batch_op:
        batch_op.drop_column("phone_carrier")
