"""Add HQ AI Task Manager tables.

Revision ID: 20260115_add_hq_ai_task
Revises: 20260114_fix_hq_employee_columns
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260115_add_hq_ai_task'
down_revision: Union[str, None] = '20260114_hq_employee_fix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types (using raw SQL to avoid SQLAlchemy trying to recreate)
    conn = op.get_bind()
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'hqaiagenttype') THEN
                CREATE TYPE hqaiagenttype AS ENUM ('oracle', 'sentinel', 'nexus');
            END IF;
        END $$;
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'hqaitaskstatus') THEN
                CREATE TYPE hqaitaskstatus AS ENUM ('queued', 'planning', 'in_progress', 'completed', 'failed');
            END IF;
        END $$;
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'hqaitaskpriority') THEN
                CREATE TYPE hqaitaskpriority AS ENUM ('low', 'normal', 'high', 'urgent');
            END IF;
        END $$;
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'hqaitaskeventtype') THEN
                CREATE TYPE hqaitaskeventtype AS ENUM ('thinking', 'action', 'result', 'error');
            END IF;
        END $$;
    """))

    # Create tables using raw SQL to bypass enum creation
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_ai_tasks (
            id VARCHAR(36) PRIMARY KEY,
            agent_type hqaiagenttype NOT NULL,
            description TEXT NOT NULL,
            priority hqaitaskpriority NOT NULL DEFAULT 'normal',
            status hqaitaskstatus NOT NULL DEFAULT 'queued',
            progress_percent INTEGER DEFAULT 0,
            result TEXT,
            error TEXT,
            context_data JSONB,
            created_by_id VARCHAR(36) REFERENCES hq_employee(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS hq_ai_task_events (
            id VARCHAR(36) PRIMARY KEY,
            task_id VARCHAR(36) NOT NULL REFERENCES hq_ai_tasks(id) ON DELETE CASCADE,
            event_type hqaitaskeventtype NOT NULL,
            content TEXT NOT NULL,
            event_metadata JSONB,
            timestamp TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

    # Add indexes
    op.create_index('ix_hq_ai_tasks_status', 'hq_ai_tasks', ['status'])
    op.create_index('ix_hq_ai_tasks_agent_type', 'hq_ai_tasks', ['agent_type'])
    op.create_index('ix_hq_ai_tasks_created_at', 'hq_ai_tasks', ['created_at'])
    op.create_index('ix_hq_ai_task_events_task_id', 'hq_ai_task_events', ['task_id'])
    op.create_index('ix_hq_ai_task_events_timestamp', 'hq_ai_task_events', ['timestamp'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_hq_ai_task_events_timestamp', table_name='hq_ai_task_events')
    op.drop_index('ix_hq_ai_task_events_task_id', table_name='hq_ai_task_events')
    op.drop_index('ix_hq_ai_tasks_created_at', table_name='hq_ai_tasks')
    op.drop_index('ix_hq_ai_tasks_agent_type', table_name='hq_ai_tasks')
    op.drop_index('ix_hq_ai_tasks_status', table_name='hq_ai_tasks')

    # Drop tables
    op.drop_table('hq_ai_task_events')
    op.drop_table('hq_ai_tasks')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS hqaitaskeventtype')
    op.execute('DROP TYPE IF EXISTS hqaitaskpriority')
    op.execute('DROP TYPE IF EXISTS hqaitaskstatus')
    op.execute('DROP TYPE IF EXISTS hqaiagenttype')
