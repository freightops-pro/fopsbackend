"""Add document processing job table

Revision ID: 20251111_000003
Revises: 20251111_000002
Create Date: 2025-11-11 16:05:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251111_000003"
down_revision = "20251111_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documentprocessingjob",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("company_id", sa.String(), sa.ForeignKey("company.id"), nullable=False, index=True),
        sa.Column("load_id", sa.String(), sa.ForeignKey("freight_load.id"), nullable=True, index=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_payload", sa.JSON(), nullable=True),
        sa.Column("field_confidence", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("documentprocessingjob")

