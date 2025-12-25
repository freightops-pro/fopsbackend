"""Add lead activities, email templates, and email config tables

Revision ID: 20251225_lead_act
Revises:
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251225_lead_act'
down_revision: Union[str, None] = '20251225_000004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create hq_lead_activities table
    op.create_table(
        'hq_lead_activities',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('lead_id', sa.String(36), sa.ForeignKey('hq_lead.id'), nullable=False, index=True),
        sa.Column('activity_type', sa.Enum(
            'note', 'email_sent', 'email_received', 'call', 'meeting',
            'follow_up', 'status_change', 'ai_action',
            name='activitytype'
        ), nullable=False),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        # Email fields
        sa.Column('email_from', sa.String(255), nullable=True),
        sa.Column('email_to', sa.String(255), nullable=True),
        sa.Column('email_cc', sa.Text, nullable=True),
        sa.Column('email_message_id', sa.String(255), nullable=True),
        sa.Column('email_thread_id', sa.String(255), nullable=True),
        sa.Column('email_status', sa.String(50), nullable=True),
        # Follow-up fields
        sa.Column('follow_up_date', sa.DateTime, nullable=True),
        sa.Column('follow_up_status', sa.Enum(
            'pending', 'due', 'completed', 'snoozed', 'cancelled',
            name='followupstatus'
        ), nullable=True),
        sa.Column('follow_up_completed_at', sa.DateTime, nullable=True),
        # Call fields
        sa.Column('call_duration_seconds', sa.String(50), nullable=True),
        sa.Column('call_outcome', sa.String(100), nullable=True),
        # Meta
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('created_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('is_pinned', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=True, onupdate=sa.func.now()),
    )
    op.create_index('ix_hq_lead_activities_lead_id', 'hq_lead_activities', ['lead_id'])
    op.create_index('ix_hq_lead_activities_activity_type', 'hq_lead_activities', ['activity_type'])
    op.create_index('ix_hq_lead_activities_follow_up_date', 'hq_lead_activities', ['follow_up_date'])

    # Create hq_email_templates table
    op.create_table(
        'hq_email_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('body', sa.Text, nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('is_global', sa.Boolean, default=True),
        sa.Column('created_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('variables', sa.JSON, nullable=True),
        sa.Column('times_used', sa.String(50), default='0'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=True, onupdate=sa.func.now()),
    )

    # Create hq_email_config table
    op.create_table(
        'hq_email_config',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('config', sa.JSON, nullable=False),
        sa.Column('from_email', sa.String(255), nullable=False),
        sa.Column('from_name', sa.String(255), nullable=True),
        sa.Column('reply_to', sa.String(255), nullable=True),
        sa.Column('is_default', sa.Boolean, default=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=True, onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('hq_email_config')
    op.drop_table('hq_email_templates')
    op.drop_index('ix_hq_lead_activities_follow_up_date', table_name='hq_lead_activities')
    op.drop_index('ix_hq_lead_activities_activity_type', table_name='hq_lead_activities')
    op.drop_index('ix_hq_lead_activities_lead_id', table_name='hq_lead_activities')
    op.drop_table('hq_lead_activities')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS followupstatus")
    op.execute("DROP TYPE IF EXISTS activitytype")
