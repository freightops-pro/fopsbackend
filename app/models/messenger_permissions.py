from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime
import uuid

class MessengerAdmin(Base):
    """Messenger administration permissions for subscriber-wide management"""
    __tablename__ = "messenger_admins"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subscriber_id = Column(String, ForeignKey("subscribers.id"), nullable=False)
    can_manage_announcements = Column(Boolean, default=False)
    can_manage_groups = Column(Boolean, default=False)
    can_moderate_messages = Column(Boolean, default=False)
    can_access_ai_settings = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("Users")
    subscriber = relationship("Subscriber")
