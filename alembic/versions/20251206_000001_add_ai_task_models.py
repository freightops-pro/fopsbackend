"""Add AI task and conversation models.

Revision ID: 20251206_000001
Revises: 20251205_000001
Create Date: 2025-12-06 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251206_000001'
down_revision = '20251205_000001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # AI Tasks Table
    op.create_table(
        'ai_tasks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('agent_type', sa.String(), nullable=False),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('input_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('planned_steps', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('current_step_index', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('executed_steps', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='queued'),
        sa.Column('priority', sa.String(), nullable=True, server_default='normal'),
        sa.Column('progress_percent', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_step', sa.Integer(), nullable=True),
        sa.Column('ai_model', sa.String(), nullable=True),
        sa.Column('total_tokens_used', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_cost_usd', sa.String(), nullable=True, server_default='0.00'),
        sa.Column('tools_used', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('execution_time_seconds', sa.Integer(), nullable=True),
        sa.Column('requires_review', sa.String(), nullable=True, server_default='false'),
        sa.Column('reviewed_by', sa.String(), nullable=True),
        sa.Column('review_decision', sa.String(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(), nullable=True),
        sa.Column('deadline', sa.DateTime(), nullable=True),
        sa.Column('recurring', sa.String(), nullable=True, server_default='false'),
        sa.Column('recurrence_rule', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_tasks_company_status', 'ai_tasks', ['company_id', 'status'])
    op.create_index('idx_ai_tasks_agent_status', 'ai_tasks', ['agent_type', 'status'])
    op.create_index('idx_ai_tasks_priority', 'ai_tasks', ['priority', 'status'])
    op.create_index('idx_ai_tasks_scheduled', 'ai_tasks', ['scheduled_for'])
    op.create_index(op.f('ix_ai_tasks_company_id'), 'ai_tasks', ['company_id'])
    op.create_index(op.f('ix_ai_tasks_user_id'), 'ai_tasks', ['user_id'])
    op.create_index(op.f('ix_ai_tasks_status'), 'ai_tasks', ['status'])
    op.create_index(op.f('ix_ai_tasks_task_type'), 'ai_tasks', ['task_type'])

    # AI Tool Executions Table
    op.create_table(
        'ai_tool_executions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('task_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=False),
        sa.Column('tool_category', sa.String(), nullable=True),
        sa.Column('input_parameters', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('output_result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_tool_executions_task', 'ai_tool_executions', ['task_id', 'created_at'])
    op.create_index('idx_ai_tool_executions_tool_status', 'ai_tool_executions', ['tool_name', 'status'])
    op.create_index(op.f('ix_ai_tool_executions_task_id'), 'ai_tool_executions', ['task_id'])
    op.create_index(op.f('ix_ai_tool_executions_company_id'), 'ai_tool_executions', ['company_id'])
    op.create_index(op.f('ix_ai_tool_executions_tool_name'), 'ai_tool_executions', ['tool_name'])

    # AI Learning Table
    op.create_table(
        'ai_learning',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('agent_type', sa.String(), nullable=False),
        sa.Column('learning_type', sa.String(), nullable=False),
        sa.Column('context', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('ai_decision', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('actual_outcome', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('feedback_score', sa.Integer(), nullable=True),
        sa.Column('human_modified', sa.String(), nullable=True, server_default='false'),
        sa.Column('modifications', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('feedback_comment', sa.Text(), nullable=True),
        sa.Column('accuracy_metric', sa.String(), nullable=True),
        sa.Column('accuracy_value', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_learning_agent_type', 'ai_learning', ['agent_type', 'learning_type'])
    op.create_index('idx_ai_learning_company', 'ai_learning', ['company_id', 'created_at'])
    op.create_index(op.f('ix_ai_learning_company_id'), 'ai_learning', ['company_id'])
    op.create_index(op.f('ix_ai_learning_agent_type'), 'ai_learning', ['agent_type'])

    # AI Conversations Table
    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('assistant_type', sa.String(), nullable=True, server_default='auto'),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('context_type', sa.String(), nullable=True),
        sa.Column('context_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='active'),
        sa.Column('message_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_message_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_conversations_company_updated', 'ai_conversations', ['company_id', 'updated_at'])
    op.create_index('idx_ai_conversations_user_updated', 'ai_conversations', ['user_id', 'updated_at'])
    op.create_index('idx_ai_conversations_context', 'ai_conversations', ['context_type', 'context_id'])
    op.create_index(op.f('ix_ai_conversations_company_id'), 'ai_conversations', ['company_id'])
    op.create_index(op.f('ix_ai_conversations_user_id'), 'ai_conversations', ['user_id'])

    # AI Messages Table
    op.create_table(
        'ai_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('assistant_type', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('tool_calls', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tool_results', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('context_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['ai_conversations.id'], )
    )
    op.create_index('idx_ai_messages_conversation_created', 'ai_messages', ['conversation_id', 'created_at'])
    op.create_index('idx_ai_messages_company_created', 'ai_messages', ['company_id', 'created_at'])
    op.create_index(op.f('ix_ai_messages_conversation_id'), 'ai_messages', ['conversation_id'])
    op.create_index(op.f('ix_ai_messages_company_id'), 'ai_messages', ['company_id'])

    # AI Context Table
    op.create_table(
        'ai_contexts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('preferred_assistant', sa.String(), nullable=True),
        sa.Column('auto_route_enabled', sa.String(), nullable=True, server_default='true'),
        sa.Column('common_customers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('common_lanes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('common_equipment', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('business_rules', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('preferred_rate_structure', sa.String(), nullable=True),
        sa.Column('timezone', sa.String(), nullable=True),
        sa.Column('units', sa.String(), nullable=True, server_default='imperial'),
        sa.Column('ai_formality', sa.String(), nullable=True, server_default='professional'),
        sa.Column('ai_verbosity', sa.String(), nullable=True, server_default='balanced'),
        sa.Column('successful_suggestions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('rejected_suggestions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id')
    )
    op.create_index(op.f('ix_ai_contexts_company_id'), 'ai_contexts', ['company_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_contexts_company_id'), table_name='ai_contexts')
    op.drop_table('ai_contexts')

    op.drop_index(op.f('ix_ai_messages_company_id'), table_name='ai_messages')
    op.drop_index(op.f('ix_ai_messages_conversation_id'), table_name='ai_messages')
    op.drop_index('idx_ai_messages_company_created', table_name='ai_messages')
    op.drop_index('idx_ai_messages_conversation_created', table_name='ai_messages')
    op.drop_table('ai_messages')

    op.drop_index(op.f('ix_ai_conversations_user_id'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_company_id'), table_name='ai_conversations')
    op.drop_index('idx_ai_conversations_context', table_name='ai_conversations')
    op.drop_index('idx_ai_conversations_user_updated', table_name='ai_conversations')
    op.drop_index('idx_ai_conversations_company_updated', table_name='ai_conversations')
    op.drop_table('ai_conversations')

    op.drop_index(op.f('ix_ai_learning_agent_type'), table_name='ai_learning')
    op.drop_index(op.f('ix_ai_learning_company_id'), table_name='ai_learning')
    op.drop_index('idx_ai_learning_company', table_name='ai_learning')
    op.drop_index('idx_ai_learning_agent_type', table_name='ai_learning')
    op.drop_table('ai_learning')

    op.drop_index(op.f('ix_ai_tool_executions_tool_name'), table_name='ai_tool_executions')
    op.drop_index(op.f('ix_ai_tool_executions_company_id'), table_name='ai_tool_executions')
    op.drop_index(op.f('ix_ai_tool_executions_task_id'), table_name='ai_tool_executions')
    op.drop_index('idx_ai_tool_executions_tool_status', table_name='ai_tool_executions')
    op.drop_index('idx_ai_tool_executions_task', table_name='ai_tool_executions')
    op.drop_table('ai_tool_executions')

    op.drop_index(op.f('ix_ai_tasks_task_type'), table_name='ai_tasks')
    op.drop_index(op.f('ix_ai_tasks_status'), table_name='ai_tasks')
    op.drop_index(op.f('ix_ai_tasks_user_id'), table_name='ai_tasks')
    op.drop_index(op.f('ix_ai_tasks_company_id'), table_name='ai_tasks')
    op.drop_index('idx_ai_tasks_scheduled', table_name='ai_tasks')
    op.drop_index('idx_ai_tasks_priority', table_name='ai_tasks')
    op.drop_index('idx_ai_tasks_agent_status', table_name='ai_tasks')
    op.drop_index('idx_ai_tasks_company_status', table_name='ai_tasks')
    op.drop_table('ai_tasks')
