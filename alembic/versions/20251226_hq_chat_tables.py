"""add_hq_chat_tables

Revision ID: 20251226_hq_chat_tables
Revises: 20251225_hq_deal_sub
Create Date: 2025-12-26 13:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB


# revision identifiers, used by Alembic.
revision = '20251226_hq_chat_tables'
down_revision = '20251225_hq_deal_sub'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create HQ Chat Channels table
    op.create_table(
        'hq_chat_channels',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('channel_type', sa.String(20), nullable=False, server_default='team'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_pinned', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('last_message', sa.Text(), nullable=True),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_chat_channels_channel_type'), 'hq_chat_channels', ['channel_type'], unique=False)

    # Create HQ Chat Messages table
    op.create_table(
        'hq_chat_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('channel_id', sa.String(), nullable=False),
        sa.Column('author_id', sa.String(), nullable=False),
        sa.Column('author_name', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_ai_response', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('ai_agent', sa.String(20), nullable=True),
        sa.Column('ai_reasoning', sa.Text(), nullable=True),
        sa.Column('ai_confidence', sa.Float(), nullable=True),
        sa.Column('attachments', JSONB(), nullable=True),
        sa.Column('mentions', ARRAY(sa.String()), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['channel_id'], ['hq_chat_channels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_chat_messages_channel_id'), 'hq_chat_messages', ['channel_id'], unique=False)
    op.create_index(op.f('ix_hq_chat_messages_author_id'), 'hq_chat_messages', ['author_id'], unique=False)
    op.create_index(op.f('ix_hq_chat_messages_created_at'), 'hq_chat_messages', ['created_at'], unique=False)

    # Create HQ Chat Participants table
    op.create_table(
        'hq_chat_participants',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('channel_id', sa.String(), nullable=False),
        sa.Column('employee_id', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('role', sa.String(50), nullable=True),
        sa.Column('is_ai', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['channel_id'], ['hq_chat_channels.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hq_chat_participants_channel_id'), 'hq_chat_participants', ['channel_id'], unique=False)
    op.create_index(op.f('ix_hq_chat_participants_employee_id'), 'hq_chat_participants', ['employee_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_hq_chat_participants_employee_id'), table_name='hq_chat_participants')
    op.drop_index(op.f('ix_hq_chat_participants_channel_id'), table_name='hq_chat_participants')
    op.drop_table('hq_chat_participants')

    op.drop_index(op.f('ix_hq_chat_messages_created_at'), table_name='hq_chat_messages')
    op.drop_index(op.f('ix_hq_chat_messages_author_id'), table_name='hq_chat_messages')
    op.drop_index(op.f('ix_hq_chat_messages_channel_id'), table_name='hq_chat_messages')
    op.drop_table('hq_chat_messages')

    op.drop_index(op.f('ix_hq_chat_channels_channel_type'), table_name='hq_chat_channels')
    op.drop_table('hq_chat_channels')
