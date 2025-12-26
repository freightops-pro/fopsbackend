"""Add presence features for chat systems

Revision ID: 20251226_presence_features
Revises: 20251226_hq_chat_tables
Create Date: 2025-12-26 14:00:00.000000

Adds:
- away_message, status_set_manually, last_activity_at to collab_presence
- hq_presence table for HQ employee presence tracking
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251226_presence_features'
down_revision = '20251226_hq_chat_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to collab_presence for tenant chat
    op.add_column('collab_presence', sa.Column('away_message', sa.Text(), nullable=True))
    op.add_column('collab_presence', sa.Column('status_set_manually', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('collab_presence', sa.Column('last_activity_at', sa.DateTime(), nullable=True))

    # Create HQ presence table
    op.create_table(
        'hq_presence',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('employee_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='offline'),
        sa.Column('away_message', sa.Text(), nullable=True),
        sa.Column('status_set_manually', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_activity_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['employee_id'], ['hq_employee.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_presence_employee_id'), 'hq_presence', ['employee_id'], unique=True)
    op.create_index(op.f('ix_hq_presence_status'), 'hq_presence', ['status'], unique=False)


def downgrade() -> None:
    # Drop HQ presence table
    op.drop_index(op.f('ix_hq_presence_status'), table_name='hq_presence')
    op.drop_index(op.f('ix_hq_presence_employee_id'), table_name='hq_presence')
    op.drop_table('hq_presence')

    # Remove columns from collab_presence
    op.drop_column('collab_presence', 'last_activity_at')
    op.drop_column('collab_presence', 'status_set_manually')
    op.drop_column('collab_presence', 'away_message')
