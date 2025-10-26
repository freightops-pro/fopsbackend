"""Add collaboration and real-time sync tables

Revision ID: 007_add_collaboration_tables
Revises: 006_add_location_tracking
Create Date: 2024-01-20 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_add_collaboration_tables'
down_revision = '006_add_location_tracking'
branch_labels = None
depends_on = None


def upgrade():
    """Add collaboration and real-time sync tables"""
    
    # WriteLock table for managing concurrent editing
    op.create_table('write_locks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('record_type', sa.String(), nullable=False),
        sa.Column('record_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('user_name', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # WriteLockRequest table for requesting write access
    op.create_table('write_lock_requests',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('record_type', sa.String(), nullable=False),
        sa.Column('record_id', sa.String(), nullable=False),
        sa.Column('requester_id', sa.String(), nullable=False),
        sa.Column('requester_name', sa.String(), nullable=False),
        sa.Column('current_locker_id', sa.String(), nullable=False),
        sa.Column('current_locker_name', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),  # pending, granted, denied, expired
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # RecordViewer table for tracking who's viewing records
    op.create_table('record_viewers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('record_type', sa.String(), nullable=False),
        sa.Column('record_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('user_name', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('viewing_since', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # RecordVersion table for version history
    op.create_table('record_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('record_type', sa.String(), nullable=False),
        sa.Column('record_id', sa.String(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('user_name', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('changes', postgresql.JSON(), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # CollaborationMessage table for real-time messaging
    op.create_table('collaboration_messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('record_type', sa.String(), nullable=False),
        sa.Column('record_id', sa.String(), nullable=False),
        sa.Column('sender_id', sa.String(), nullable=False),
        sa.Column('sender_name', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('message_type', sa.String(), nullable=False),  # comment, mention, system
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('mentions', postgresql.JSON(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance
    op.create_index('idx_write_locks_record', 'write_locks', ['record_type', 'record_id'])
    op.create_index('idx_write_locks_user', 'write_locks', ['user_id'])
    op.create_index('idx_write_locks_company', 'write_locks', ['company_id'])
    op.create_index('idx_write_locks_active', 'write_locks', ['is_active', 'expires_at'])
    
    op.create_index('idx_write_lock_requests_record', 'write_lock_requests', ['record_type', 'record_id'])
    op.create_index('idx_write_lock_requests_requester', 'write_lock_requests', ['requester_id'])
    op.create_index('idx_write_lock_requests_status', 'write_lock_requests', ['status', 'expires_at'])
    
    op.create_index('idx_record_viewers_record', 'record_viewers', ['record_type', 'record_id'])
    op.create_index('idx_record_viewers_user', 'record_viewers', ['user_id'])
    op.create_index('idx_record_viewers_active', 'record_viewers', ['is_active', 'last_activity'])
    
    op.create_index('idx_record_versions_record', 'record_versions', ['record_type', 'record_id'])
    op.create_index('idx_record_versions_user', 'record_versions', ['user_id'])
    
    op.create_index('idx_collaboration_messages_record', 'collaboration_messages', ['record_type', 'record_id'])
    op.create_index('idx_collaboration_messages_sender', 'collaboration_messages', ['sender_id'])
    op.create_index('idx_collaboration_messages_created', 'collaboration_messages', ['created_at'])


def downgrade():
    """Remove collaboration and real-time sync tables"""
    
    # Drop indexes
    op.drop_index('idx_collaboration_messages_created', 'collaboration_messages')
    op.drop_index('idx_collaboration_messages_sender', 'collaboration_messages')
    op.drop_index('idx_collaboration_messages_record', 'collaboration_messages')
    
    op.drop_index('idx_record_versions_user', 'record_versions')
    op.drop_index('idx_record_versions_record', 'record_versions')
    
    op.drop_index('idx_record_viewers_active', 'record_viewers')
    op.drop_index('idx_record_viewers_user', 'record_viewers')
    op.drop_index('idx_record_viewers_record', 'record_viewers')
    
    op.drop_index('idx_write_lock_requests_status', 'write_lock_requests')
    op.drop_index('idx_write_lock_requests_requester', 'write_lock_requests')
    op.drop_index('idx_write_lock_requests_record', 'write_lock_requests')
    
    op.drop_index('idx_write_locks_active', 'write_locks')
    op.drop_index('idx_write_locks_company', 'write_locks')
    op.drop_index('idx_write_locks_user', 'write_locks')
    op.drop_index('idx_write_locks_record', 'write_locks')
    
    # Drop tables
    op.drop_table('collaboration_messages')
    op.drop_table('record_versions')
    op.drop_table('record_viewers')
    op.drop_table('write_lock_requests')
    op.drop_table('write_locks')
