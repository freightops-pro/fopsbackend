from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime
import uuid

class Subscriber(Base):
    """Subscriber model - top-level entity above companies for multi-tenant SaaS"""
    __tablename__ = "subscribers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    primary_admin_id = Column(String, ForeignKey("users.id"), nullable=True)
    subscription_tier = Column(String, nullable=False, default="starter")  # starter, professional, enterprise
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    # companies = relationship("Companies", back_populates="subscriber")  # Not in Neon DB schema
    primary_admin = relationship("Users", foreign_keys=[primary_admin_id])

