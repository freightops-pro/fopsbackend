"""Track NeonDB branches for agent sandboxing.

Revision ID: 20251214_000003
Revises: 20251214_000002
Create Date: 2025-12-14 00:00:03.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '20251214_000003'
down_revision = '20251214_000002'
branch_labels = None
depends_on = None


def upgrade():
    """Create ai_database_branches table for NeonDB sandboxing."""
    op.create_table(
        'ai_database_branches',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('task_id', sa.String(), nullable=False, index=True),
        sa.Column('company_id', sa.String(), nullable=False),

        # Neon branch info
        sa.Column('neon_branch_id', sa.String(), nullable=False),
        sa.Column('neon_branch_name', sa.String(), nullable=False),
        sa.Column('branch_connection_uri', sa.Text(), nullable=True),  # Encrypted

        # Purpose
        sa.Column('purpose', sa.String(), nullable=False),  # sandbox_test, what_if_analysis
        sa.Column('agent_type', sa.String(), nullable=False),

        # SQL to test
        sa.Column('proposed_sql', sa.Text(), nullable=True),
        sa.Column('sql_executed', sa.Text(), nullable=True),
        sa.Column('affected_rows', sa.Integer(), nullable=True),

        # Audit results
        sa.Column('auditor_agent', sa.String(), nullable=True),  # adam
        sa.Column('audit_decision', sa.String(), nullable=True),  # approved, rejected
        sa.Column('audit_reasoning', sa.Text(), nullable=True),

        # Lifecycle
        sa.Column('status', sa.String(), default='active'),  # active, merged, deleted
        sa.Column('merged_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
    )

    # Create indexes
    op.create_index('idx_neon_branches_task', 'ai_database_branches', ['task_id'])
    op.create_index('idx_neon_branches_status', 'ai_database_branches', ['status', 'created_at'])


def downgrade():
    """Drop ai_database_branches table."""
    op.drop_index('idx_neon_branches_status', table_name='ai_database_branches')
    op.drop_index('idx_neon_branches_task', table_name='ai_database_branches')
    op.drop_table('ai_database_branches')
