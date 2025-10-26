from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, func, Integer, Text, JSON, Enum
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.config.db import Base
import uuid
import enum

# Enums for chat functionality
class MessageType(str, enum.Enum):
    TEXT = "text"
    SYSTEM = "system"  # System notifications

class ConversationType(str, enum.Enum):
    DIRECT = "direct"  # 1-on-1 conversations (existing)
    TEAM = "team"      # Team/group conversations (Enterprise only)
    ANNOUNCEMENT = "announcement"  # Subscriber-wide announcements
    GROUP = "group"    # User-created group chats
    AI_CONVERSATION = "ai_conversation"  # Conversations with AI assistants

# SQLAlchemy Models

class Conversation(Base):
    """Chat conversations between users and drivers - supports both 1-on-1 and team chats"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscriber_id = Column(String(36), ForeignKey("subscribers.id"), nullable=True)  # Subscriber-wide conversations
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    
    # Conversation type: direct, team, announcement, group, ai_conversation
    conversation_type = Column(Enum(ConversationType), nullable=False, default=ConversationType.DIRECT)
    
    # For direct conversations (existing functionality)
    # Can be user-user, user-driver, or driver-driver
    participant1_id = Column(String(36), nullable=True)  # Generic ID (user or driver)
    participant2_id = Column(String(36), nullable=True)  # Generic ID (user or driver)
    participant1_type = Column(String(10), nullable=True)  # 'user', 'driver', or 'ai'
    participant2_type = Column(String(10), nullable=True)  # 'user', 'driver', or 'ai'
    
    # For team conversations (Enterprise only)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)  # References teams table
    team_name = Column(String(255), nullable=True)  # Cache team name for performance
    
    # For AI conversations
    ai_source = Column(String(20), nullable=True)  # 'annie', 'alex', 'atlas'
    is_ai_conversation = Column(Boolean, default=False)
    
    # For group conversations
    group_name = Column(String(255), nullable=True)
    group_description = Column(Text, nullable=True)
    
    # For announcements
    is_announcement = Column(Boolean, default=False)
    announcement_title = Column(String(255), nullable=True)
    
    # Metadata
    last_message_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(36), nullable=False)  # Generic ID (user or driver)
    created_by_type = Column(String(10), nullable=False)  # 'user' or 'driver'
    is_active = Column(Boolean, default=True)

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    subscriber = relationship("Subscriber")
    company = relationship("Companies", backref="conversations")

class ConversationReadStatus(Base):
    """Read status for each participant in a conversation"""
    __tablename__ = "conversation_read_status"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    participant_id = Column(String(36), nullable=False)  # Generic ID (user or driver)
    participant_type = Column(String(10), nullable=False)  # 'user' or 'driver'
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    
    # Read Status
    last_read_at = Column(DateTime, nullable=True)
    unread_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    conversation = relationship("Conversation", backref="read_statuses")

class Message(Base):
    """Simple chat messages"""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(String(36), nullable=False)  # Generic ID (user or driver)
    sender_type = Column(String(10), nullable=False)  # 'user' or 'driver'
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False)
    
    # Message Content
    content = Column(Text, nullable=False)
    message_type = Column(Enum(MessageType), nullable=False, default=MessageType.TEXT)
    
    # Reply Support
    reply_to_message_id = Column(String(36), ForeignKey("messages.id"), nullable=True)
    
    # Message Status
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    reply_to = relationship("Message", remote_side=[id], backref="replies")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")

# Pydantic Models for API

class ConversationBase(BaseModel):
    pass

class ConversationCreate(ConversationBase):
    other_participant_id: str  # The other participant to chat with (user or driver)
    other_participant_type: str  # 'user' or 'driver'

class ConversationUpdate(BaseModel):
    pass  # No updates needed for 1-on-1 chats

class ConversationResponse(ConversationBase):
    id: str
    company_id: str
    participant1_id: str
    participant2_id: str
    participant1_type: str
    participant2_type: str
    last_message_at: Optional[datetime] = None
    message_count: int
    created_at: datetime
    updated_at: datetime
    created_by: str
    created_by_type: str
    is_active: bool

    class Config:
        from_attributes = True

class ConversationReadStatusBase(BaseModel):
    pass

class ConversationReadStatusResponse(ConversationReadStatusBase):
    id: str
    conversation_id: str
    participant_id: str
    participant_type: str
    company_id: str
    last_read_at: Optional[datetime] = None
    unread_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageBase(BaseModel):
    content: str
    message_type: MessageType = MessageType.TEXT
    reply_to_message_id: Optional[str] = None

class MessageCreate(MessageBase):
    conversation_id: str

class MessageUpdate(BaseModel):
    content: Optional[str] = None

class MessageResponse(MessageBase):
    id: str
    conversation_id: str
    sender_id: str
    sender_type: str
    company_id: str
    is_deleted: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Additional response models for complex queries

class ConversationWithDetails(ConversationResponse):
    other_participant: Optional[dict] = None  # Basic info about the other participant
    unread_count: int = 0

class MessageWithDetails(MessageResponse):
    sender: Optional[dict] = None  # Basic sender info
    reply_to_message: Optional[MessageResponse] = None

class ConversationSummary(BaseModel):
    """Summary for conversation list"""
    id: str
    other_participant_id: str
    other_participant_type: str
    other_participant_name: Optional[str] = None
    last_message_content: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int

class ChatStats(BaseModel):
    """Chat statistics for dashboard"""
    total_conversations: int
    total_messages: int
    unread_messages: int
    active_conversations: int
    messages_today: int
    messages_this_week: int