"""fix_conversation_read_status_table

Revision ID: 811bf06e0056
Revises: c25ffbe4a32a
Create Date: 2025-09-26 21:06:07.133884

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '811bf06e0056'
down_revision: Union[str, None] = 'c25ffbe4a32a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update conversation_read_status table to match the model
    op.execute("""
        CREATE TABLE conversation_read_status_new (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            participant_id VARCHAR(36) NOT NULL,
            participant_type VARCHAR(10) NOT NULL,
            company_id VARCHAR(36) NOT NULL,
            last_read_at TIMESTAMP,
            unread_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    """)
    
    # Copy data from old table, mapping user_id to participant_id and setting participant_type to 'user'
    op.execute("""
        INSERT INTO conversation_read_status_new (
            id, conversation_id, participant_id, participant_type, company_id, 
            last_read_at, unread_count, created_at, updated_at
        )
        SELECT 
            id, conversation_id, user_id, 'user', company_id,
            last_read_at, unread_count, created_at, updated_at
        FROM conversation_read_status
    """)
    
    # Drop old table and rename new one
    op.execute("DROP TABLE conversation_read_status")
    op.execute("ALTER TABLE conversation_read_status_new RENAME TO conversation_read_status")


def downgrade() -> None:
    # Recreate table with old schema (for rollback)
    op.execute("""
        CREATE TABLE conversation_read_status_old (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            company_id VARCHAR(36) NOT NULL,
            last_read_at TIMESTAMP,
            unread_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    """)
    
    # Copy data back, mapping participant_id to user_id
    op.execute("""
        INSERT INTO conversation_read_status_old (
            id, conversation_id, user_id, company_id, 
            last_read_at, unread_count, created_at, updated_at
        )
        SELECT 
            id, conversation_id, participant_id, company_id,
            last_read_at, unread_count, created_at, updated_at
        FROM conversation_read_status
    """)
    
    # Drop and rename
    op.execute("DROP TABLE conversation_read_status")
    op.execute("ALTER TABLE conversation_read_status_old RENAME TO conversation_read_status")
