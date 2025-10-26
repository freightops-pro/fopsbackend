from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.config.db import Base


class WriteLock(Base):
    """Model for managing write locks on records for collaborative editing"""
    __tablename__ = "write_locks"

    id = Column(Integer, primary_key=True, index=True)
    record_type = Column(String(50), nullable=False, index=True)  # load, invoice, settlement, customer, driver
    record_id = Column(String(100), nullable=False, index=True)
    
    # Current editor info
    current_editor_id = Column(String, ForeignKey("users.id"), nullable=False)
    current_editor = relationship("Users", foreign_keys=[current_editor_id])
    acquired_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_activity_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Company for multi-tenant isolation
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    company = relationship("Companies")
    
    # Lock metadata
    is_active = Column(Boolean, default=True)
    lock_type = Column(String(20), default="edit")  # edit, force_take, admin_override
    
    # Unique constraint: one active lock per record
    __table_args__ = (
        Index('idx_active_record_lock', 'record_type', 'record_id', 'is_active', unique=True, 
              postgresql_where=Column('is_active') == True),
        Index('idx_company_locks', 'company_id', 'is_active'),
    )


class WriteLockRequest(Base):
    """Model for tracking write lock access requests"""
    __tablename__ = "write_lock_requests"

    id = Column(Integer, primary_key=True, index=True)
    lock_id = Column(Integer, ForeignKey("write_locks.id"), nullable=False)
    lock = relationship("WriteLock")
    
    # Requester info
    requester_id = Column(String, ForeignKey("users.id"), nullable=False)
    requester = relationship("Users", foreign_keys=[requester_id])
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Request status
    status = Column(String(20), default="pending")  # pending, granted, denied, cancelled
    responded_at = Column(DateTime(timezone=True), nullable=True)
    response_by_id = Column(String, ForeignKey("users.id"), nullable=True)
    response_by = relationship("Users", foreign_keys=[response_by_id])
    
    # Company for multi-tenant isolation
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_pending_requests', 'lock_id', 'status'),
        Index('idx_company_requests', 'company_id', 'status'),
    )


class RecordViewer(Base):
    """Model for tracking active viewers of a record"""
    __tablename__ = "record_viewers"

    id = Column(Integer, primary_key=True, index=True)
    record_type = Column(String(50), nullable=False, index=True)
    record_id = Column(String(100), nullable=False, index=True)
    
    # Viewer info
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user = relationship("Users")
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Company for multi-tenant isolation
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    # Viewer status
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        Index('idx_active_viewers', 'record_type', 'record_id', 'is_active'),
        Index('idx_company_viewers', 'company_id', 'user_id'),
    )


class RecordVersion(Base):
    """Model for tracking record version history"""
    __tablename__ = "record_versions"

    id = Column(Integer, primary_key=True, index=True)
    record_type = Column(String(50), nullable=False, index=True)
    record_id = Column(String(100), nullable=False, index=True)
    
    # Version info
    version_number = Column(Integer, nullable=False)
    changes = Column(JSON, nullable=False)  # Field-level change tracking
    full_snapshot = Column(JSON, nullable=True)  # Complete record snapshot
    
    # Change attribution
    changed_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    changed_by = relationship("Users")
    changed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Change metadata
    change_summary = Column(Text, nullable=True)
    change_type = Column(String(20), default="edit")  # edit, create, delete, restore
    
    # Company for multi-tenant isolation
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_record_versions', 'record_type', 'record_id', 'version_number'),
        Index('idx_company_versions', 'company_id', 'changed_at'),
    )


class CollaborationMessage(Base):
    """Model for in-context chat messages within records"""
    __tablename__ = "collaboration_messages"

    id = Column(Integer, primary_key=True, index=True)
    record_type = Column(String(50), nullable=False, index=True)
    record_id = Column(String(100), nullable=False, index=True)
    
    # Message info
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    sender = relationship("Users")
    message = Column(Text, nullable=False)
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Message metadata
    mentions = Column(JSON, nullable=True)  # Array of user IDs mentioned
    attachments = Column(JSON, nullable=True)  # Array of file attachments
    is_system_message = Column(Boolean, default=False)
    
    # Company for multi-tenant isolation
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_record_messages', 'record_type', 'record_id', 'sent_at'),
        Index('idx_company_messages', 'company_id', 'sent_at'),
    )

