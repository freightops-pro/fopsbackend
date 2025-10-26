from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from app.config.db import Base
from datetime import datetime
import uuid

class AIInsight(Base):
    """AI-generated insights from Annie, Alex, and Atlas"""
    __tablename__ = "ai_insights"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subscriber_id = Column(String, ForeignKey("subscribers.id"), nullable=False)
    ai_source = Column(Enum('annie', 'alex', 'atlas', name='ai_source_enum'), nullable=False)
    function_category = Column(String, nullable=False)  # accounting, payroll, dispatch, safety, banking, loadboard, etc.
    insight_type = Column(String, nullable=False)  # suggestion, alert, report, prediction, analysis
    priority = Column(Enum('critical', 'high', 'medium', 'low', name='priority_enum'), nullable=False, default='medium')
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    data = Column(JSON, nullable=True)  # Structured data for the insight
    status = Column(Enum('pending', 'accepted', 'dismissed', name='insight_status_enum'), nullable=False, default='pending')
    target_users = Column(JSON, nullable=True)  # Specific user IDs or roles to notify
    created_at = Column(DateTime, default=datetime.utcnow)
    dismissed_at = Column(DateTime, nullable=True)
    dismissed_by = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    subscriber = relationship("Subscriber")
    dismissed_by_user = relationship("Users", foreign_keys=[dismissed_by])
