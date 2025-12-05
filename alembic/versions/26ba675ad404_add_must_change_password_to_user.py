"""add_must_change_password_to_user

Revision ID: 26ba675ad404
Revises: e9f31e598fb6
Create Date: 2025-11-28 23:21:36.620442

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26ba675ad404'
down_revision = 'e9f31e598fb6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add must_change_password column to user table
    op.add_column('user', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    # Remove must_change_password column from user table
    op.drop_column('user', 'must_change_password')

