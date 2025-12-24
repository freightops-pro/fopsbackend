"""Add HR fields to hq_employee table

Revision ID: 20251224_000002
Revises: 20251224_000001
Create Date: 2024-12-24 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251224_000002'
down_revision: Union[str, None] = '20251224_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new HR fields to hq_employee table
    op.add_column('hq_employee', sa.Column('title', sa.String(), nullable=True))
    op.add_column('hq_employee', sa.Column('hire_date', sa.DateTime(), nullable=True))
    op.add_column('hq_employee', sa.Column('salary', sa.Integer(), nullable=True))
    op.add_column('hq_employee', sa.Column('emergency_contact', sa.String(), nullable=True))
    op.add_column('hq_employee', sa.Column('emergency_phone', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('hq_employee', 'emergency_phone')
    op.drop_column('hq_employee', 'emergency_contact')
    op.drop_column('hq_employee', 'salary')
    op.drop_column('hq_employee', 'hire_date')
    op.drop_column('hq_employee', 'title')
