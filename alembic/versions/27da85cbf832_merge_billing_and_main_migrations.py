"""merge billing and main migrations

Revision ID: 27da85cbf832
Revises: 20251207_000002, 20251212_000001
Create Date: 2025-12-12 20:47:43.501832

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '27da85cbf832'
down_revision = ('20251207_000002', '20251212_000001')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

