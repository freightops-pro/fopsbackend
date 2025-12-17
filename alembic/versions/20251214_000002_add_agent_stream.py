"""Add real-time agent execution stream table.

Revision ID: 20251214_000002
Revises: 20251214_000001
Create Date: 2025-12-14 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '20251214_000002'
down_revision = '20251214_000001'
branch_labels = None
depends_on = None


def upgrade():
    """Create ai_agent_stream table for real-time visibility."""
    op.create_table(
        'ai_agent_stream',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('task_id', sa.String(), nullable=False, index=True),
        sa.Column('company_id', sa.String(), nullable=False, index=True),

        # Agent info
        sa.Column('agent_type', sa.String(), nullable=False),  # annie, adam, atlas
        sa.Column('event_type', sa.String(), nullable=False),  # thinking, tool_call, result, decision, rejection

        # Content
        sa.Column('message', sa.Text(), nullable=False),  # Human-readable message
        sa.Column('metadata', sa.JSON(), nullable=True),  # Additional context
        sa.Column('reasoning', sa.Text(), nullable=True),  # AI's reasoning/thought process

        # Status
        sa.Column('severity', sa.String(), default='info'),  # info, warning, error, success
        sa.Column('step_number', sa.Integer(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow, nullable=False),
    )

    # Create indexes for efficient queries
    op.create_index('idx_agent_stream_task_created', 'ai_agent_stream', ['task_id', 'created_at'])
    op.create_index('idx_agent_stream_company', 'ai_agent_stream', ['company_id', 'created_at'])


def downgrade():
    """Drop ai_agent_stream table."""
    op.drop_index('idx_agent_stream_company', table_name='ai_agent_stream')
    op.drop_index('idx_agent_stream_task_created', table_name='ai_agent_stream')
    op.drop_table('ai_agent_stream')
