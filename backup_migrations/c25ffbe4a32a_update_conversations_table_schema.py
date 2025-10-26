"""update_conversations_table_schema

Revision ID: c25ffbe4a32a
Revises: 1851b353dec5
Create Date: 2025-09-26 21:03:26.327447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c25ffbe4a32a'
down_revision: Union[str, None] = '1851b353dec5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    # Create new table with correct schema
    op.execute("""
        CREATE TABLE conversations_new (
            id VARCHAR(36) PRIMARY KEY,
            company_id VARCHAR(36) NOT NULL,
            participant1_id VARCHAR(36) NOT NULL,
            participant2_id VARCHAR(36) NOT NULL,
            participant1_type VARCHAR(10) NOT NULL,
            participant2_type VARCHAR(10) NOT NULL,
            last_message_at TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(36) NOT NULL,
            created_by_type VARCHAR(10) NOT NULL,
            is_active BOOLEAN DEFAULT true,
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    """)
    
    # Copy data from old table, mapping old columns to new ones
    # For existing data, we'll assume both participants are users
    op.execute("""
        INSERT INTO conversations_new (
            id, company_id, participant1_id, participant2_id, 
            participant1_type, participant2_type, last_message_at, 
            message_count, created_at, updated_at, created_by, 
            created_by_type, is_active
        )
        SELECT 
            id, company_id, user1_id, user2_id,
            'user', 'user', last_message_at,
            message_count, created_at, updated_at, created_by,
            'user', is_active
        FROM conversations
    """)
    
    # Drop old table and rename new one
    op.execute("DROP TABLE conversations")
    op.execute("ALTER TABLE conversations_new RENAME TO conversations")
    
    # Also update messages table to add sender_type column
    op.execute("""
        CREATE TABLE messages_new (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            sender_id VARCHAR(36) NOT NULL,
            sender_type VARCHAR(10) NOT NULL,
            company_id VARCHAR(36) NOT NULL,
            content TEXT NOT NULL,
            message_type VARCHAR(20) NOT NULL,
            reply_to_message_id VARCHAR(36),
            is_deleted BOOLEAN DEFAULT false,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (reply_to_message_id) REFERENCES messages (id)
        )
    """)
    
    # Copy data from old messages table, assuming sender_type is 'user' for existing data
    op.execute("""
        INSERT INTO messages_new (
            id, conversation_id, sender_id, sender_type, company_id, 
            content, message_type, reply_to_message_id, is_deleted, 
            deleted_at, created_at, updated_at
        )
        SELECT 
            id, conversation_id, sender_id, 'user', company_id,
            content, message_type, reply_to_message_id, is_deleted,
            deleted_at, created_at, updated_at
        FROM messages
    """)
    
    # Drop old messages table and rename new one
    op.execute("DROP TABLE messages")
    op.execute("ALTER TABLE messages_new RENAME TO messages")
    
    # Also update conversation_read_status table
    op.execute("""
        CREATE TABLE conversation_read_status_new (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            participant_id VARCHAR(36) NOT NULL,
            participant_type VARCHAR(10) NOT NULL,
            company_id VARCHAR(36) NOT NULL,
            last_read_at DATETIME,
            unread_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    """)
    
    # Copy data from old conversation_read_status table, assuming participant_type is 'user' for existing data
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
    
    # Drop old conversation_read_status table and rename new one
    op.execute("DROP TABLE conversation_read_status")
    op.execute("ALTER TABLE conversation_read_status_new RENAME TO conversation_read_status")


def downgrade() -> None:
    # Recreate table with old schema (for rollback)
    op.execute("""
        CREATE TABLE conversations_old (
            id VARCHAR(36) PRIMARY KEY,
            company_id VARCHAR(36) NOT NULL,
            user1_id VARCHAR(36) NOT NULL,
            user2_id VARCHAR(36) NOT NULL,
            last_message_at TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(36) NOT NULL,
            is_active BOOLEAN DEFAULT true,
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    """)
    
    # Copy data back, mapping new columns to old ones
    op.execute("""
        INSERT INTO conversations_old (
            id, company_id, user1_id, user2_id, last_message_at, 
            message_count, created_at, updated_at, created_by, is_active
        )
        SELECT 
            id, company_id, participant1_id, participant2_id, 
            last_message_at, message_count, created_at, updated_at, 
            created_by, is_active
        FROM conversations
    """)
    
    # Drop and rename
    op.execute("DROP TABLE conversations")
    op.execute("ALTER TABLE conversations_old RENAME TO conversations")
    
    # Also revert messages table
    op.execute("""
        CREATE TABLE messages_old (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            sender_id VARCHAR(36) NOT NULL,
            company_id VARCHAR(36) NOT NULL,
            content TEXT NOT NULL,
            message_type VARCHAR(20) NOT NULL,
            reply_to_message_id VARCHAR(36),
            is_deleted BOOLEAN DEFAULT false,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (company_id) REFERENCES companies (id),
            FOREIGN KEY (reply_to_message_id) REFERENCES messages (id)
        )
    """)
    
    # Copy data back, removing sender_type column
    op.execute("""
        INSERT INTO messages_old (
            id, conversation_id, sender_id, company_id, 
            content, message_type, reply_to_message_id, is_deleted, 
            deleted_at, created_at, updated_at
        )
        SELECT 
            id, conversation_id, sender_id, company_id,
            content, message_type, reply_to_message_id, is_deleted,
            deleted_at, created_at, updated_at
        FROM messages
    """)
    
    # Drop and rename
    op.execute("DROP TABLE messages")
    op.execute("ALTER TABLE messages_old RENAME TO messages")
    
    # Also revert conversation_read_status table
    op.execute("""
        CREATE TABLE conversation_read_status_old (
            id VARCHAR(36) PRIMARY KEY,
            conversation_id VARCHAR(36) NOT NULL,
            user_id VARCHAR(36) NOT NULL,
            company_id VARCHAR(36) NOT NULL,
            last_read_at DATETIME,
            unread_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id),
            FOREIGN KEY (company_id) REFERENCES companies (id)
        )
    """)
    
    # Copy data back, removing participant_type column
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
