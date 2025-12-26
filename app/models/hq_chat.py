"""HQ Chat Models - Unified Team + AI Chat."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


class HQChatChannel(Base):
    """HQ Chat Channel - team channels and AI channel."""

    __tablename__ = "hq_chat_channels"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    channel_type = Column(String(20), nullable=False, default="team")  # team, ai, direct, announcement
    description = Column(Text, nullable=True)
    is_pinned = Column(Boolean, default=False)
    last_message = Column(Text, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=True)  # Employee ID who created the channel
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    messages = relationship("HQChatMessage", back_populates="channel", cascade="all, delete-orphan")
    participants = relationship("HQChatParticipant", back_populates="channel", cascade="all, delete-orphan")


class HQChatMessage(Base):
    """HQ Chat Message - supports both human and AI messages."""

    __tablename__ = "hq_chat_messages"

    id = Column(String, primary_key=True)
    channel_id = Column(String, ForeignKey("hq_chat_channels.id", ondelete="CASCADE"), nullable=False)
    author_id = Column(String, nullable=False)  # Employee ID or AI agent ID
    author_name = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    # AI-specific fields
    is_ai_response = Column(Boolean, default=False)
    ai_agent = Column(String(20), nullable=True)  # oracle, sentinel, nexus
    ai_reasoning = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)

    # File attachments - JSON array of attachment objects
    # Each attachment: {id, filename, file_type, file_size, url, thumbnail_url}
    attachments = Column(JSONB, nullable=True)

    # Metadata
    mentions = Column(ARRAY(String), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    channel = relationship("HQChatChannel", back_populates="messages")


class HQChatParticipant(Base):
    """HQ Chat Participant - tracks channel membership."""

    __tablename__ = "hq_chat_participants"

    id = Column(String, primary_key=True)
    channel_id = Column(String, ForeignKey("hq_chat_channels.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(String, nullable=False)
    display_name = Column(String(200), nullable=False)
    role = Column(String(50), nullable=True)  # admin, member
    is_ai = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    channel = relationship("HQChatChannel", back_populates="participants")
