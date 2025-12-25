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
    # Create enum types for AI queue (with IF NOT EXISTS equivalent)
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
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_ai_actions (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            action_type aiactiontype NOT NULL,
            risk_level aiactionrisk NOT NULL DEFAULT 'medium',
            status aiactionstatus NOT NULL DEFAULT 'pending',
            agent_name VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            draft_content TEXT,
            ai_reasoning TEXT,
            entity_type VARCHAR(50),
            entity_id VARCHAR(36),
            entity_name VARCHAR(255),
            risk_factors JSON,
            entity_data JSON,
            assigned_to_id VARCHAR(36) REFERENCES hq_employee(id),
            reviewed_by_id VARCHAR(36) REFERENCES hq_employee(id),
            reviewed_at TIMESTAMP,
            human_edits TEXT,
            rejection_reason TEXT,
            was_edited BOOLEAN DEFAULT FALSE,
            edit_similarity_score INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            executed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_ai_actions_status ON hq_ai_actions(status);
        CREATE INDEX IF NOT EXISTS ix_hq_ai_actions_agent_name ON hq_ai_actions(agent_name);
        CREATE INDEX IF NOT EXISTS ix_hq_ai_actions_entity_id ON hq_ai_actions(entity_id);
    """)

    # Create hq_ai_autonomy_rules table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_ai_autonomy_rules (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            action_type aiactiontype NOT NULL,
            agent_name VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            condition_field VARCHAR(100) NOT NULL,
            condition_operator VARCHAR(20) NOT NULL,
            condition_value VARCHAR(255) NOT NULL,
            resulting_risk aiactionrisk NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            priority INTEGER DEFAULT 0,
            total_actions INTEGER DEFAULT 0,
            approved_without_edits INTEGER DEFAULT 0,
            approved_with_edits INTEGER DEFAULT 0,
            rejected INTEGER DEFAULT 0,
            auto_promote_threshold INTEGER DEFAULT 95,
            is_level_3_enabled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_ai_autonomy_rules_action_type ON hq_ai_autonomy_rules(action_type);
        CREATE INDEX IF NOT EXISTS ix_hq_ai_autonomy_rules_agent_name ON hq_ai_autonomy_rules(agent_name);
    """)


def downgrade() -> None:
    # Drop tables
    op.execute("DROP TABLE IF EXISTS hq_ai_autonomy_rules")
    op.execute("DROP TABLE IF EXISTS hq_ai_actions")

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS aiactionstatus')
    op.execute('DROP TYPE IF EXISTS aiactionrisk')
    op.execute('DROP TYPE IF EXISTS aiactiontype')
