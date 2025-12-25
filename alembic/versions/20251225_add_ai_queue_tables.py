"""Add HQ AI Queue tables for Level 2 autonomy

Revision ID: 20251225_ai_queue
Revises: 20251225_fmcsa
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251225_ai_queue'
down_revision: Union[str, None] = '20251225_fmcsa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types for AI queue
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE aiactiontype AS ENUM (
                'lead_outreach', 'lead_qualification', 'rate_negotiation',
                'load_acceptance', 'driver_assignment', 'compliance_alert', 'invoice_approval'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE aiactionrisk AS ENUM ('low', 'medium', 'high', 'critical');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE aiactionstatus AS ENUM (
                'pending', 'approved', 'approved_with_edits', 'rejected', 'auto_executed', 'expired'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create hq_ai_actions table
    op.create_table(
        'hq_ai_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('action_type', sa.Enum('lead_outreach', 'lead_qualification', 'rate_negotiation',
                                          'load_acceptance', 'driver_assignment', 'compliance_alert',
                                          'invoice_approval', name='aiactiontype', create_type=False), nullable=False),
        sa.Column('risk_level', sa.Enum('low', 'medium', 'high', 'critical', name='aiactionrisk', create_type=False),
                  nullable=False, server_default='medium'),
        sa.Column('status', sa.Enum('pending', 'approved', 'approved_with_edits', 'rejected', 'auto_executed', 'expired',
                                     name='aiactionstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('agent_name', sa.String(50), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('draft_content', sa.Text, nullable=True),
        sa.Column('ai_reasoning', sa.Text, nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('entity_name', sa.String(255), nullable=True),
        sa.Column('risk_factors', sa.JSON, nullable=True),
        sa.Column('entity_data', sa.JSON, nullable=True),
        sa.Column('assigned_to_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('reviewed_by_id', sa.String(36), sa.ForeignKey('hq_employee.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime, nullable=True),
        sa.Column('human_edits', sa.Text, nullable=True),
        sa.Column('rejection_reason', sa.Text, nullable=True),
        sa.Column('was_edited', sa.Boolean, default=False),
        sa.Column('edit_similarity_score', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('executed_at', sa.DateTime, nullable=True),
    )

    # Create indexes for hq_ai_actions
    op.create_index('ix_hq_ai_actions_status', 'hq_ai_actions', ['status'])
    op.create_index('ix_hq_ai_actions_agent_name', 'hq_ai_actions', ['agent_name'])
    op.create_index('ix_hq_ai_actions_entity_id', 'hq_ai_actions', ['entity_id'])

    # Create hq_ai_autonomy_rules table
    op.create_table(
        'hq_ai_autonomy_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('action_type', sa.Enum('lead_outreach', 'lead_qualification', 'rate_negotiation',
                                          'load_acceptance', 'driver_assignment', 'compliance_alert',
                                          'invoice_approval', name='aiactiontype', create_type=False), nullable=False),
        sa.Column('agent_name', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('condition_field', sa.String(100), nullable=False),
        sa.Column('condition_operator', sa.String(20), nullable=False),
        sa.Column('condition_value', sa.String(255), nullable=False),
        sa.Column('resulting_risk', sa.Enum('low', 'medium', 'high', 'critical', name='aiactionrisk', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('total_actions', sa.Integer, default=0),
        sa.Column('approved_without_edits', sa.Integer, default=0),
        sa.Column('approved_with_edits', sa.Integer, default=0),
        sa.Column('rejected', sa.Integer, default=0),
        sa.Column('auto_promote_threshold', sa.Integer, default=95),
        sa.Column('is_level_3_enabled', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=True, onupdate=sa.func.now()),
    )

    # Create indexes for hq_ai_autonomy_rules
    op.create_index('ix_hq_ai_autonomy_rules_action_type', 'hq_ai_autonomy_rules', ['action_type'])
    op.create_index('ix_hq_ai_autonomy_rules_agent_name', 'hq_ai_autonomy_rules', ['agent_name'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('hq_ai_autonomy_rules')
    op.drop_table('hq_ai_actions')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS aiactionstatus')
    op.execute('DROP TYPE IF EXISTS aiactionrisk')
    op.execute('DROP TYPE IF EXISTS aiactiontype')
