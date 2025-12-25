"""Add lead activities, email templates, and email config tables

Revision ID: 20251225_lead_act
Revises: 20251225_000004
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
    # Create enum types if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE activitytype AS ENUM (
                'note', 'email_sent', 'email_received', 'call', 'meeting',
                'follow_up', 'status_change', 'ai_action'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE followupstatus AS ENUM (
                'pending', 'due', 'completed', 'snoozed', 'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Create hq_lead_activities table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_lead_activities (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            lead_id VARCHAR(36) NOT NULL REFERENCES hq_lead(id),
            activity_type activitytype NOT NULL,
            subject VARCHAR(500),
            content TEXT,
            email_from VARCHAR(255),
            email_to VARCHAR(255),
            email_cc TEXT,
            email_message_id VARCHAR(255),
            email_thread_id VARCHAR(255),
            email_status VARCHAR(50),
            follow_up_date TIMESTAMP,
            follow_up_status followupstatus,
            follow_up_completed_at TIMESTAMP,
            call_duration_seconds VARCHAR(50),
            call_outcome VARCHAR(100),
            metadata JSON,
            created_by_id VARCHAR(36) REFERENCES hq_employee(id),
            is_pinned BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS ix_hq_lead_activities_lead_id ON hq_lead_activities(lead_id);
        CREATE INDEX IF NOT EXISTS ix_hq_lead_activities_activity_type ON hq_lead_activities(activity_type);
        CREATE INDEX IF NOT EXISTS ix_hq_lead_activities_follow_up_date ON hq_lead_activities(follow_up_date);
    """)

    # Create hq_email_templates table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_email_templates (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            subject VARCHAR(500) NOT NULL,
            body TEXT NOT NULL,
            category VARCHAR(100),
            is_global BOOLEAN DEFAULT TRUE,
            created_by_id VARCHAR(36) REFERENCES hq_employee(id),
            variables JSON,
            times_used VARCHAR(50) DEFAULT '0',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)

    # Create hq_email_config table
    op.execute("""
        CREATE TABLE IF NOT EXISTS hq_email_config (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            provider VARCHAR(50) NOT NULL,
            config JSON NOT NULL,
            from_email VARCHAR(255) NOT NULL,
            from_name VARCHAR(255),
            reply_to VARCHAR(255),
            is_default BOOLEAN DEFAULT FALSE,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS hq_email_config")
    op.execute("DROP TABLE IF EXISTS hq_email_templates")
    op.execute("DROP TABLE IF EXISTS hq_lead_activities")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS followupstatus")
    op.execute("DROP TYPE IF EXISTS activitytype")
