"""Add HQ Admin table

Revision ID: 002_add_hq_admin
Revises: 001_complete_models
Create Date: 2024-01-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002_add_hq_admin'
down_revision = '001_complete_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create hq_admins table
    op.create_table('hq_admins',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False, default='hq_admin'),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_hq_admins_id'), 'hq_admins', ['id'], unique=False)
    op.create_index(op.f('ix_hq_admins_email'), 'hq_admins', ['email'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_hq_admins_email'), table_name='hq_admins')
    op.drop_index(op.f('ix_hq_admins_id'), table_name='hq_admins')
    
    # Drop table
    op.drop_table('hq_admins')
