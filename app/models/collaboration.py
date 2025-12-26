from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class Channel(Base):
    __tablename__ = "collab_channel"

    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("company.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    channel_type = Column(String, nullable=True, default="dm")  # dm, group, driver
    created_by = Column(String, ForeignKey("user.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")
    participants = relationship("ChannelParticipant", back_populates="channel", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "collab_message"

    id = Column(String, primary_key=True)
    channel_id = Column(String, ForeignKey("collab_channel.id"), nullable=False, index=True)
    author_id = Column(String, ForeignKey("user.id"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    channel = relationship("Channel", back_populates="messages")


class Presence(Base):
    """User presence status for collaboration channels.

    Tracks online/away/offline status with optional away messages
    and automatic status detection based on activity.
    """
    __tablename__ = "collab_presence"

    id = Column(String, primary_key=True)
    channel_id = Column(String, ForeignKey("collab_channel.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("user.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="online")  # online, away, offline
    away_message = Column(Text, nullable=True)  # Custom away message
    status_set_manually = Column(Boolean, nullable=False, default=False)  # If true, don't auto-away
    last_activity_at = Column(DateTime, nullable=True)  # Last user activity for idle detection
    last_seen_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class ChannelParticipant(Base):
    __tablename__ = "collab_channel_participant"

    id = Column(String, primary_key=True)
    channel_id = Column(String, ForeignKey("collab_channel.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("user.id"), nullable=True, index=True)
    driver_id = Column(String, ForeignKey("driver.id"), nullable=True, index=True)
    display_name = Column(String, nullable=False)
    added_at = Column(DateTime, nullable=False, server_default=func.now())

    channel = relationship("Channel", back_populates="participants")

