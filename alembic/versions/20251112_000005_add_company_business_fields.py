"""Add business metadata to company

Revision ID: 20251112_000005
Revises: 20251111_000004
Create Date: 2025-11-12 22:10:00

"""

from alembic import op
import sqlalchemy as sa


revision = "20251112_000005"
down_revision = "20251111_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("company") as batch_op:
        batch_op.add_column(sa.Column("business_type", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("dot_number", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("mc_number", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("primary_contact_name", sa.String(), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.create_unique_constraint("uq_company_dot_number", "company", ["dot_number"])
        op.create_unique_constraint("uq_company_mc_number", "company", ["mc_number"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("uq_company_mc_number", "company", type_="unique")
        op.drop_constraint("uq_company_dot_number", "company", type_="unique")

    with op.batch_alter_table("company") as batch_op:
        batch_op.drop_column("primary_contact_name")
        batch_op.drop_column("mc_number")
        batch_op.drop_column("dot_number")
        batch_op.drop_column("business_type")

