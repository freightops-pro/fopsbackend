"""Add user_id to driver for app access linking

Revision ID: 20251112_000006
Revises: 20251112_000005
Create Date: 2025-11-12 23:00:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20251112_000006"
down_revision = "20251112_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("driver") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(), nullable=True))
    
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_driver_user_id",
            "driver",
            "user",
            ["user_id"],
            ["id"],
            ondelete="SET NULL"
        )
        op.create_index("ix_driver_user_id", "driver", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_index("ix_driver_user_id", "driver")
        op.drop_constraint("fk_driver_user_id", "driver", type_="foreignkey")
    
    with op.batch_alter_table("driver") as batch_op:
        batch_op.drop_column("user_id")

