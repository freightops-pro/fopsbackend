from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime
import uuid

class MessageAttachment(Base):
    """File attachments for messenger messages"""
    __tablename__ = "message_attachments"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id = Column(String, ForeignKey("messages.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # image, document, video, audio
    file_size = Column(Integer, nullable=False)  # bytes
    file_path = Column(String, nullable=False)
    thumbnail_path = Column(String, nullable=True)  # for images/videos
    mime_type = Column(String, nullable=False)
    uploaded_by = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    message = relationship("Message", back_populates="attachments")
    uploader = relationship("Users")
