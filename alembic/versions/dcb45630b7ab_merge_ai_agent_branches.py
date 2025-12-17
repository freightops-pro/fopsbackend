"""merge ai agent branches

Revision ID: dcb45630b7ab
Revises: 20251214_000003, 7c9362e64b1a
Create Date: 2025-12-14 22:56:44.998792

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dcb45630b7ab'
down_revision = ('20251214_000003', '7c9362e64b1a')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

